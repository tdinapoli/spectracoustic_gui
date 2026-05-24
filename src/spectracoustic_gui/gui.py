from pathlib import Path
from typing import TypedDict

from nicegui import ui, run

import photoacoustic.main as pa_main
import numpy as np


class AnalysisDirectory(TypedDict):
    path: str | Path


def update_plot():
    with ui.matplotlib(figsize=(4, 4)).figure as fig:
        x = np.linspace(0, 2, 100)
        y = np.sin(2 * np.pi * x)
        ax = fig.gca()
        ax.plot(x, y)


# 1. FIX THE ANALYSIS FUNCTION: Run it in a separate process
async def pa_main_wrapper(analysis_dir: AnalysisDirectory):
    if not analysis_dir["path"]:
        ui.notify("Please select a directory first!", type="warning")
        return

    ui.notify("Starting photoacoustic analysis script...", type="info")

    # run.cpu_bound drops the function into a separate process,
    # keeping the NiceGUI event loop completely free and fluid.
    await run.cpu_bound(pa_main.main, analysis_dir["path"])

    ui.notify("Analysis complete!", type="positive")


def pa_make_done_file(analysis_dir: AnalysisDirectory):
    print("making done file")
    p = Path(analysis_dir["path"]) / "done.txt"
    with open(p, "w") as f:
        print("done", file=f)


def askdirectory_wrapper(analysis_dir: AnalysisDirectory, dir_path: str | Path | None):
    if dir_path is None:
        ui.notify("Please input a directory path", type="info")
        return

    try:
        dir_path = Path(dir_path)
    except ValueError as e:
        ui.notify(f"Couldn't build path from input with error {e}", type="negative")

    ui.notify(f"Directory selected: {dir_path}", type="positive")
    analysis_dir["path"] = dir_path


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

    with ui.column().classes("w-full items-center"):
        ui.markdown("# Photoacoustic Analysis 💥🎙️")

        # 1. Create the button first (sits on top)
        dir_btn = ui.button(text="Select analysis directory")

        dir_path = ui.input(label="Data directory path:")
        label = ui.label().bind_text_from(dir_path, "value")

        # 3. Attach the click handler now that dir_display exists
        dir_btn.on("click", lambda: askdirectory_wrapper(analysis_dir, label.text))

        ui.button(text="Run analysis", on_click=lambda: pa_main_wrapper(analysis_dir))

        ui.button(
            text="Measurements done", on_click=lambda: pa_make_done_file(analysis_dir)
        )

        ui.button(text="Update plot", on_click=lambda: update_plot())


def main():
    # Force native=True if you want it to open in a dedicated Chromium window
    # instead of a generic browser tab on the lab computer!
    ui.run(title="SpectraCoustic UI", port=8080, reload=False)


if __name__ in {"__main__", "pkt_fields"}:
    main()
