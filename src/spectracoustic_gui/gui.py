import io
import base64
from pathlib import Path
import time
from typing import TypedDict, get_args

from nicegui import ui, run

import photoacoustic.main as pa_main
from photoacoustic.constants import Options, PaSignal
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import pickle


UPDATE_PLOT_TIMER: float = 2.0


class AnalysisDirectory(TypedDict):
    path: str | Path


def get_linear_plot_if_changed(root: Path, fig_relative_path: str) -> Figure | None:
    figpath = root / fig_relative_path

    if not figpath.exists():
        return

    mtime = figpath.stat().st_mtime
    ctime = figpath.stat().st_ctime
    now = time.time()
    if (now - mtime) > UPDATE_PLOT_TIMER and (now - ctime) > UPDATE_PLOT_TIMER:
        return

    try:
        with open(figpath, "rb") as f:
            fig = pickle.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        ui.notify(f"Couldn't load figure with error {e}", type="negative")
    return fig


def update_plot(root: Path, plot_image: ui.image, fig_relative_path: str):
    fig = get_linear_plot_if_changed(root, fig_relative_path)
    if not fig:
        return

    try:
        # 1. Save the detached figure directly to an in-memory buffer
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        buf.seek(0)

        # 2. Convert the image bytes to a base64 string
        img_base64 = base64.b64encode(buf.read()).decode("utf-8")

        # 3. Display it using NiceGUI's native image element via Data URI
        plot_image.set_source(f"data:image/png;base64,{img_base64}")

    except Exception as e:
        ui.notify(f"couldn't display figure with error {e}", type="negative")


def directory_is_valid(dir_path: str | Path) -> bool:
    if not dir_path:
        ui.notify("Please select a directory first!", type="warning")
        return False

    try:
        dir_path = Path(dir_path)
    except ValueError as e:
        ui.notify(f"Couldn't build path from input with error {e}", type="negative")
        return False

    ui.notify(f"Directory selected: {dir_path}", type="positive")
    return True


# 1. FIX THE ANALYSIS FUNCTION: Run it in a separate process
async def pa_main_wrapper(
    label: ui.label,
    analysis_dir: AnalysisDirectory,
    linear_plot_image: ui.image,
    last_plot_image: ui.image,
):
    path = label.text
    if not directory_is_valid(path):
        return
    try:
        path = Path(path)
        analysis_dir["path"] = path
    except Exception as e:
        ui.notify(e, type="negative")
        return

    # linear plot image timer
    linear_plot_timer = ui.timer(
        UPDATE_PLOT_TIMER,
        lambda: update_plot(path, linear_plot_image, "_figures/__linear_fit.pickle"),
    )
    last_plot_timer = ui.timer(
        UPDATE_PLOT_TIMER,
        lambda: update_plot(path, last_plot_image, "_figures/__last_plot.pickle"),
    )
    ui.notify("Starting photoacoustic analysis script...", type="info")

    # run.cpu_bound drops the function into a separate process,
    # keeping the NiceGUI event loop completely free and fluid.
    await run.cpu_bound(pa_main.main, path)

    linear_plot_timer.cancel()
    last_plot_timer.cancel()
    ui.notify("Analysis complete!", type="positive")


def pa_make_done_file(analysis_dir: AnalysisDirectory):
    try:
        p = Path(analysis_dir["path"]) / "done.txt"
        with open(p, "w") as f:
            print("done", file=f)
    except Exception as e:
        ui.notify(f"Failed to create done file with error {e}", type="negative")
    ui.notify("Finishing analysis...", type="info")


def root():
    ui.sub_pages(
        {
            "/": select_page,
        }
    ).classes("w-full")


@ui.page("/")
def select_page():
    analysis_dir = AnalysisDirectory(path="")

    container_row = ui.row().classes("w-full gap-8 wrap")
    with container_row:
        upper_row = ui.column().classes("w-full items-stretch items-center shrink-0")
        options_row = ui.row().classes("w-full items-stretch items-center")
        lower_row = ui.column().classes("w-full items-stretch")

        with upper_row:
            ui.markdown("# Photoacoustic Analysis 💥🎙️")
            settings_container = ui.row().classes("w-full items-center items-stretch")

        with options_row:
            ui.markdown("Options")
            with ui.column().classes("flex-1 items-stretch"):
                ui.checkbox("Plot timetrace for repeats", value=True)
                ui.checkbox("Plot nonzero intercept", value=True)
                ui.checkbox("Plot uncertainty slope", value=False)
                ui.checkbox("Plot uncertainty slope0", value=True)
            with ui.column().classes("flex-1 items-stretch"):
                ui.number("Max Energy", value=50.0)
                ui.number("Reference alpha value", value=1.0)
                ui.number("Threshold factor", value=2.0)
                ui.select(options=list(get_args(PaSignal)), value="signal_delta")

        with lower_row:
            plots_row = ui.row().classes("w-full gap-4 wrap items-stretch")
            with plots_row:
                ui.label("Live data view").classes("text-xl font-bold text-grey-7")
                left_plot_col = ui.column().classes(
                    "flex-1 min-w-[400px] items-stretch"
                )
                right_plot_col = ui.column().classes(
                    "flex-1 min-w-[400px] items-stretch"
                )

                with left_plot_col:
                    linear_plot_container = ui.card().classes("w-full items-center")

                with right_plot_col:
                    last_plot_container = ui.card().classes("w-full items-center")

    with linear_plot_container:
        linear_plot_image = ui.image()

    with last_plot_container:
        last_plot_image = ui.image()

    plots_row.set_visibility(False)
    with settings_container:
        dir_path = ui.input(label="Data directory path:").classes("flex-1")

        label = ui.label().bind_text_from(dir_path, "value")
        label.set_visibility(False)

        async def handle_run_click():
            # 1. Hide the options row (or settings_container, depending on which one you want to hide!)
            options_row.set_visibility(False)
            plots_row.set_visibility(True)

            # 2. Fire off the background analysis wrapper
            await pa_main_wrapper(
                label, analysis_dir, linear_plot_image, last_plot_image
            )

            plots_row.set_visibility(False)
            options_row.set_visibility(True)

        ui.button(
            text="Run",
            on_click=lambda: handle_run_click(),
        )

        ui.button(text="Finish", on_click=lambda: pa_make_done_file(analysis_dir))


def main():
    # Force native=True if you want it to open in a dedicated Chromium window
    # instead of a generic browser tab on the lab computer!
    ui.run(title="SpectraCoustic UI", port=8080, reload=True)


if __name__ in {"__main__", "__mp_main__"}:
    main()
