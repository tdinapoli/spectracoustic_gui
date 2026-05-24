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
async def pa_main_wrapper(label: ui.label, analysis_dir: AnalysisDirectory):
    path = label.text
    if not directory_is_valid(path):
        return
    try:
        path = Path(path)
        analysis_dir["path"] = path
    except Exception as e:
        ui.notify(e, type="negative")

    ui.notify("Starting photoacoustic analysis script...", type="info")

    # run.cpu_bound drops the function into a separate process,
    # keeping the NiceGUI event loop completely free and fluid.
    await run.cpu_bound(pa_main.main, path)

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

    with ui.column().classes("w-[400 px] items-center items-stretch"):
        ui.markdown("# Photoacoustic Analysis 💥🎙️")

        dir_path = ui.input(label="Data directory path:")
        label = ui.label().bind_text_from(dir_path, "value")

        ui.button(
            text="Run analysis", on_click=lambda: pa_main_wrapper(label, analysis_dir)
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
