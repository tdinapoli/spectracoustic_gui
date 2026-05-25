import io
import base64
from pathlib import Path
import time
from typing import TypedDict

from nicegui import ui, run

import photoacoustic.main as pa_main
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

    ui.markdown("# Photoacoustic Analysis 💥🎙️")
    settings_container = ui.column().classes("w-[800px] items-center items-stretch")
    linear_plot_container = ui.card().classes("w-[800px] items-center mt-4")
    last_plot_container = ui.card().classes("w-[800px] items-center mt-4")

    with linear_plot_container:
        linear_plot_image = ui.image()

    with last_plot_container:
        last_plot_image = ui.image()

    with settings_container:
        dir_path = ui.input(label="Data directory path:")

        label = ui.label().bind_text_from(dir_path, "value")

        ui.button(
            text="Run analysis",
            on_click=lambda: pa_main_wrapper(
                label, analysis_dir, linear_plot_image, last_plot_image
            ),
        )

        ui.button(
            text="Measurements done", on_click=lambda: pa_make_done_file(analysis_dir)
        )


def main():
    # Force native=True if you want it to open in a dedicated Chromium window
    # instead of a generic browser tab on the lab computer!
    ui.run(title="SpectraCoustic UI", port=8080, reload=True)


if __name__ in {"__main__", "__mp_main__"}:
    main()
