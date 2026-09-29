from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app.physical_devices import enumerate_physical_devices, physical_reader_factory, validate_output_destination
from app.recovery import RecoveryEngine


class DriveRecoveryGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Drive Recovery")

        # Give the GUI enough space for the results table.
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        self.source_path = tk.StringVar()
        self.source_mode = tk.StringVar(value="image")
        self.device_path = tk.StringVar()
        self.output_path = tk.StringVar(value="recovered")
        self.status_text = tk.StringVar(value="Ready")
        self.devices = []

        self.last_output_path: Path | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=24)
        main.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(
            main,
            text="Drive Recovery",
            font=("Segoe UI", 22, "bold"),
        )
        title.pack(anchor=tk.W)

        mode_frame = ttk.LabelFrame(main, text="Source Type", padding=8)
        mode_frame.pack(fill=tk.X, pady=(12, 12))
        ttk.Radiobutton(mode_frame, text="Disk Image", variable=self.source_mode, value="image", command=self._update_source_mode).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="Physical Drive", variable=self.source_mode, value="physical", command=self._update_source_mode).pack(side=tk.LEFT, padx=(18, 0))

        subtitle = ttk.Label(
            main,
            text="Recover supported files from .img and .dd disk images",
            font=("Segoe UI", 10),
        )
        subtitle.pack(anchor=tk.W, pady=(4, 24))

        # Source
        self.source_frame = ttk.LabelFrame(
            main,
            text="Source Disk Image",
            padding=12,
        )
        self.source_frame.pack(fill=tk.X, pady=(0, 12))

        source_entry = ttk.Entry(
            self.source_frame,
            textvariable=self.source_path,
        )
        source_entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        ttk.Button(
            self.source_frame,
            text="Browse...",
            command=self._browse_source,
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        self.device_frame = ttk.LabelFrame(main, text="Physical Storage Device", padding=12)
        self.device_combo = ttk.Combobox(self.device_frame, textvariable=self.device_path, state="readonly")
        self.device_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(self.device_frame, text="Refresh Devices", command=self._refresh_devices).pack(side=tk.LEFT, padx=(8, 0))

        # Output
        output_frame = ttk.LabelFrame(
            main,
            text="Output Directory",
            padding=12,
        )
        output_frame.pack(
            fill=tk.X,
            pady=(0, 16),
        )

        output_entry = ttk.Entry(
            output_frame,
            textvariable=self.output_path,
        )
        output_entry.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

        ttk.Button(
            output_frame,
            text="Browse...",
            command=self._browse_output,
        ).pack(
            side=tk.LEFT,
            padx=(8, 0),
        )

        # Recover button
        self.recover_button = ttk.Button(
            main,
            text="Recover Files",
            command=self._start_recovery,
        )
        self.recover_button.pack(
            fill=tk.X,
            ipady=8,
        )

        # Open output folder button
        self.open_output_button = ttk.Button(
            main,
            text="Open Output Folder",
            command=self._open_output_folder,
            state=tk.DISABLED,
        )
        self.open_output_button.pack(
            fill=tk.X,
            ipady=6,
            pady=(8, 0),
        )

        # Status
        status_frame = ttk.LabelFrame(
            main,
            text="Status",
            padding=12,
        )
        status_frame.pack(
            fill=tk.X,
            pady=(16, 12),
        )

        ttk.Label(
            status_frame,
            textvariable=self.status_text,
        ).pack(anchor=tk.W)

        self.progress = ttk.Progressbar(
            status_frame,
            mode="indeterminate",
        )
        self.progress.pack(
            fill=tk.X,
            pady=(10, 0),
        )

        # Results
        results_frame = ttk.LabelFrame(
            main,
            text="Recovery Results",
            padding=12,
        )

        # IMPORTANT:
        # This frame expands to use all remaining window space.
        results_frame.pack(
            fill=tk.BOTH,
            expand=True,
        )

        columns = (
            "id",
            "type",
            "status",
            "size",
            "confidence",
        )

        self.results = ttk.Treeview(
            results_frame,
            columns=columns,
            show="headings",
        )

        self.results.heading(
            "id",
            text="ID",
        )
        self.results.heading(
            "type",
            text="Type",
        )
        self.results.heading(
            "status",
            text="Status",
        )
        self.results.heading(
            "size",
            text="Size",
        )
        self.results.heading(
            "confidence",
            text="Confidence",
        )

        self.results.column(
            "id",
            width=130,
            anchor=tk.CENTER,
        )
        self.results.column(
            "type",
            width=100,
            anchor=tk.CENTER,
        )
        self.results.column(
            "status",
            width=180,
            anchor=tk.CENTER,
        )
        self.results.column(
            "size",
            width=130,
            anchor=tk.CENTER,
        )
        self.results.column(
            "confidence",
            width=130,
            anchor=tk.CENTER,
        )

        scrollbar = ttk.Scrollbar(
            results_frame,
            orient=tk.VERTICAL,
            command=self.results.yview,
        )

        self.results.configure(
            yscrollcommand=scrollbar.set,
        )

        self.results.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
        )

        scrollbar.pack(
            side=tk.RIGHT,
            fill=tk.Y,
        )
        self._update_source_mode()

    def _update_source_mode(self) -> None:
        if self.source_mode.get() == "physical":
            self.source_frame.pack_forget()
            if not self.device_frame.winfo_manager():
                self.device_frame.pack(fill=tk.X, pady=(0, 12))
            self._refresh_devices()
        else:
            self.device_frame.pack_forget()
            if not self.source_frame.winfo_manager():
                self.source_frame.pack(fill=tk.X, pady=(0, 12))

    def _refresh_devices(self) -> None:
        self.devices = enumerate_physical_devices()
        self.device_combo["values"] = [f"{device.path} | {device.model} | {device.capacity_label} | {device.media_type}" for device in self.devices]
        if self.devices:
            self.device_combo.current(0)
            self.device_path.set(self.devices[0].path)
        else:
            self.device_path.set("")

    def _browse_source(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Disk Image",
            filetypes=[
                ("Disk Images", "*.img *.dd"),
                ("IMG files", "*.img"),
                ("DD files", "*.dd"),
                ("All files", "*.*"),
            ],
        )

        if path:
            self.source_path.set(path)

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(
            title="Select Output Directory",
        )

        if path:
            self.output_path.set(path)

    def _start_recovery(self) -> None:
        source = self.source_path.get().strip()
        output = self.output_path.get().strip()

        if self.source_mode.get() == "physical":
            source = self.device_path.get().strip()

        if not source:
            messagebox.showerror(
                "Missing Source",
                "Please select a disk image or physical device.",
            )
            return

        if not output:
            messagebox.showerror(
                "Missing Output",
                "Please select an output directory.",
            )
            return

        source_path = Path(source)
        reader_factory = None
        if self.source_mode.get() == "physical":
            try:
                validate_output_destination(source, output)
                reader_factory = physical_reader_factory(source)
            except (OSError, ValueError) as exc:
                messagebox.showerror("Invalid Physical Device", str(exc))
                return
        else:
            if not source_path.exists() or not source_path.is_file():
                messagebox.showerror("Invalid Source", f"The selected source is not a readable file:\n{source}")
                return

        self._clear_results()

        self.recover_button.config(
            state=tk.DISABLED,
        )

        self.open_output_button.config(
            state=tk.DISABLED,
        )

        self.status_text.set(
            "Scanning and recovering..."
        )

        self.progress.start(10)

        thread = threading.Thread(
            target=self._run_recovery,
            args=(
                source_path,
                Path(output),
                reader_factory,
            ),
            daemon=True,
        )

        thread.start()

    def _run_recovery(
        self,
        source_path: str | Path,
        output_path: Path,
        reader_factory=None,
    ) -> None:
        try:
            engine = RecoveryEngine(
                source_path,
                output_path,
                reader_factory=reader_factory,
            )

            result = engine.recover()

            self.root.after(
                0,
                self._show_results,
                result,
            )

        except Exception as exc:
            self.root.after(
                0,
                self._show_error,
                exc,
            )

    def _show_results(self, result) -> None:
        self.progress.stop()

        self.recover_button.config(
            state=tk.NORMAL,
        )

        self.last_output_path = Path(
            result.output_dir
        )

        if (
            self.last_output_path.exists()
            and self.last_output_path.is_dir()
        ):
            self.open_output_button.config(
                state=tk.NORMAL,
            )

        for artifact in result.recovered_files:
            self.results.insert(
                "",
                tk.END,
                values=(
                    artifact.recovery_id,
                    artifact.file_type,
                    artifact.status,
                    f"{artifact.size} bytes",
                    f"{artifact.confidence:.3f}",
                ),
            )

        recovered = sum(
            1
            for item in result.recovered_files
            if item.status == "RECONSTRUCTED"
        )

        partial = sum(
            1
            for item in result.recovered_files
            if item.status == "PARTIAL"
        )

        rejected = sum(
            1
            for item in result.recovered_files
            if item.status == "REJECTED"
        )

        self.status_text.set(
            f"Complete — "
            f"Found: {result.candidates_found} | "
            f"Recovered: {recovered} | "
            f"Partial: {partial} | "
            f"Rejected: {rejected}"
        )

        if result.errors:
            messagebox.showwarning(
                "Recovery Completed with Errors",
                "\n".join(result.errors),
            )

        elif result.warnings:
            messagebox.showinfo(
                "Recovery Completed",
                f"Recovery finished with warnings.\n\n"
                f"Found: {result.candidates_found}\n"
                f"Recovered: {recovered}\n"
                f"Partial: {partial}\n"
                f"Rejected: {rejected}\n\n"
                f"Output: {result.output_dir}",
            )

        else:
            messagebox.showinfo(
                "Recovery Completed",
                f"Recovery completed successfully.\n\n"
                f"Found: {result.candidates_found}\n"
                f"Recovered: {recovered}\n"
                f"Partial: {partial}\n"
                f"Rejected: {rejected}\n\n"
                f"Output: {result.output_dir}",
            )

    def _open_output_folder(self) -> None:
        if self.last_output_path is None:
            return

        if not self.last_output_path.exists():
            messagebox.showerror(
                "Output Not Found",
                f"The output directory does not exist:\n"
                f"{self.last_output_path}",
            )
            return

        try:
            os.startfile(self.last_output_path)

        except OSError as exc:
            messagebox.showerror(
                "Unable to Open Folder",
                str(exc),
            )

    def _show_error(self, exc: Exception) -> None:
        self.progress.stop()

        self.recover_button.config(
            state=tk.NORMAL,
        )

        self.status_text.set(
            "Recovery failed."
        )

        messagebox.showerror(
            "Recovery Error",
            str(exc),
        )

    def _clear_results(self) -> None:
        for item in self.results.get_children():
            self.results.delete(item)


def main() -> None:
    root = tk.Tk()
    DriveRecoveryGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()