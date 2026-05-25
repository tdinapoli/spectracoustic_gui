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


def get_linear_plot_if_changed(root: Path) -> Figure | None:
    figpath = root / "_figures" / "__linear_fit.pickle"

    if not figpath.exists():
        return

    if time.time() - figpath.stat().st_mtime > 2:
        return

    try:
        with open(figpath, "rb") as f:
            fig = pickle.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        ui.notify(f"Couldn't load figure with error {e}", type="negative")
    return fig


def update_plot(root: Path, plot_image: ui.image):
    fig = get_linear_plot_if_changed(root)
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
    label: ui.label, analysis_dir: AnalysisDirectory, plot_image: ui.image
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

    plot_timer = ui.timer(UPDATE_PLOT_TIMER, lambda: update_plot(path, plot_image))
    ui.notify("Starting photoacoustic analysis script...", type="info")

    # run.cpu_bound drops the function into a separate process,
    # keeping the NiceGUI event loop completely free and fluid.
    await run.cpu_bound(pa_main.main, path)

    plot_timer.cancel()
    ui.notify("Analysis complete!", type="positive")


def pa_make_done_file(analysis_dir: AnalysisDirectory):
    print("making done file")
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


def print_list(result_list):
    print(result_list)


@ui.page("/")
def select_page():
    analysis_dir = AnalysisDirectory(path="")

    ui.markdown("# Photoacoustic Analysis 💥🎙️")
    settings_container = ui.column().classes("w-[800px] items-center items-stretch")
    image_container = ui.card().classes("w-[800px] items-center mt-4")

    with image_container:
        plot_image = ui.image()

    with settings_container:
        dir_path = ui.input(label="Data directory path:")

        label = ui.label().bind_text_from(dir_path, "value")

        ui.button(
            text="Run analysis",
            on_click=lambda: pa_main_wrapper(label, analysis_dir, plot_image),
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
