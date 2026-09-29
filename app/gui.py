from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from app.physical_devices import (
    enumerate_physical_devices,
    physical_reader_factory,
    validate_output_destination,
)
from app.recovery import RecoveryEngine


class DriveRecoveryGUI:
    # ---------------------------------------------------------
    # COLORS
    # ---------------------------------------------------------

    BG = "#F4F7FB"
    CARD = "#FFFFFF"
    NAVY = "#0F172A"
    TEXT = "#172033"
    MUTED = "#64748B"
    BORDER = "#E2E8F0"

    BLUE = "#2563EB"
    BLUE_HOVER = "#1D4ED8"
    BLUE_LIGHT = "#EFF6FF"

    GREEN = "#0F766E"
    GREEN_LIGHT = "#ECFDF5"

    AMBER = "#B45309"
    AMBER_LIGHT = "#FFFBEB"

    RED = "#B42318"
    RED_LIGHT = "#FEF2F2"

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root

        self.root.title("Zero Trace — Drive Recovery")
        self.root.geometry("1120x800")
        self.root.minsize(950, 680)
        self.root.configure(fg_color=self.BG)

        # -----------------------------------------------------
        # VARIABLES
        # -----------------------------------------------------

        self.source_mode = tk.StringVar(value="image")

        self.source_path = tk.StringVar()
        self.device_path = tk.StringVar()
        self.output_path = tk.StringVar(value="recovered")

        self.status_text = tk.StringVar(value="Ready")
        self.status_detail = tk.StringVar(
            value="Select a recovery source to begin."
        )
        self.progress_text = tk.StringVar(value="0%")

        self.metric_found = tk.StringVar(value="0")
        self.metric_recovered = tk.StringVar(value="0")
        self.metric_partial = tk.StringVar(value="0")
        self.metric_rejected = tk.StringVar(value="0")

        self.devices = []
        self.last_output_path: Path | None = None

        # -----------------------------------------------------
        # CUSTOMTKINTER
        # -----------------------------------------------------

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._configure_treeview()
        self._build_ui()
        self._update_source_mode()

    # =========================================================
    # TREEVIEW STYLE
    # =========================================================

    def _configure_treeview(self) -> None:
        style = ttk.Style()

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "ZeroTrace.Treeview",
            background="#FFFFFF",
            fieldbackground="#FFFFFF",
            foreground=self.TEXT,
            rowheight=34,
            borderwidth=0,
            font=("Segoe UI", 9),
        )

        style.configure(
            "ZeroTrace.Treeview.Heading",
            background="#F1F5F9",
            foreground=self.TEXT,
            relief="flat",
            borderwidth=0,
            padding=(10, 9),
            font=("Segoe UI", 9, "bold"),
        )

        style.map(
            "ZeroTrace.Treeview",
            background=[("selected", "#DBEAFE")],
            foreground=[("selected", self.TEXT)],
        )

    # =========================================================
    # MAIN UI
    # =========================================================

    def _build_ui(self) -> None:

        # -----------------------------------------------------
        # HEADER
        # -----------------------------------------------------

        header = ctk.CTkFrame(
            self.root,
            fg_color=self.NAVY,
            corner_radius=0,
            height=88,
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        header_left = ctk.CTkFrame(
            header,
            fg_color="transparent",
        )

        header_left.pack(
            side="left",
            padx=30,
            pady=15,
        )

        ctk.CTkLabel(
            header_left,
            text="ZERO TRACE",
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                family="Segoe UI",
                size=25,
                weight="bold",
            ),
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_left,
            text="Digital Forensics  •  Drive Recovery",
            text_color="#CBD5E1",
            font=ctk.CTkFont(
                family="Segoe UI",
                size=10,
            ),
        ).pack(anchor="w")

        # Read-only badge

        ctk.CTkLabel(
            header,
            text="●  READ-ONLY MODE",
            text_color="#A7F3D0",
            fg_color="#123B35",
            corner_radius=15,
            padx=14,
            pady=7,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
        ).pack(
            side="right",
            padx=30,
        )

        # -----------------------------------------------------
        # SCROLLABLE CONTENT
        # -----------------------------------------------------

        scroll = ctk.CTkScrollableFrame(
            self.root,
            fg_color=self.BG,
            corner_radius=0,
            scrollbar_button_color="#CBD5E1",
            scrollbar_button_hover_color="#94A3B8",
        )

        scroll.pack(
            fill="both",
            expand=True,
        )

        content = ctk.CTkFrame(
            scroll,
            fg_color="transparent",
        )

        content.pack(
            fill="both",
            expand=True,
            padx=28,
            pady=24,
        )

        # =====================================================
        # SOURCE CARD
        # =====================================================

        source_card = self._create_card(content)

        source_card.pack(
            fill="x",
            pady=(0, 14),
        )

        source_header = ctk.CTkFrame(
            source_card,
            fg_color="transparent",
        )

        source_header.pack(
            fill="x",
            padx=20,
            pady=(17, 5),
        )

        ctk.CTkLabel(
            source_header,
            text="RECOVERY SOURCE",
            text_color=self.TEXT,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=12,
                weight="bold",
            ),
        ).pack(side="left")

        self.source_badge = ctk.CTkLabel(
            source_header,
            text="DISK IMAGE",
            text_color=self.BLUE,
            fg_color=self.BLUE_LIGHT,
            corner_radius=6,
            padx=9,
            pady=4,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=8,
                weight="bold",
            ),
        )

        self.source_badge.pack(side="right")

        # -----------------------------------------------------
        # SOURCE SWITCH
        # -----------------------------------------------------

        self.mode_selector = ctk.CTkSegmentedButton(
            source_card,
            values=[
                "Disk Image",
                "Physical Drive",
            ],
            command=self._change_source_mode,
            selected_color=self.BLUE,
            selected_hover_color=self.BLUE_HOVER,
            unselected_color="#E8EEF6",
            unselected_hover_color="#DCE6F2",
            text_color=self.TEXT,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=10,
                weight="bold",
            ),
            height=40,
            corner_radius=9,
        )

        self.mode_selector.pack(
            anchor="w",
            padx=20,
            pady=(8, 6),
        )

        self.mode_selector.set("Disk Image")

        self.source_description = ctk.CTkLabel(
            source_card,
            text="Select a disk image (.img or .dd) as the recovery source.",
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
            ),
        )

        self.source_description.pack(
            anchor="w",
            padx=20,
            pady=(0, 12),
        )

        # -----------------------------------------------------
        # DISK IMAGE SOURCE
        # -----------------------------------------------------

        self.image_source_frame = ctk.CTkFrame(
            source_card,
            fg_color="transparent",
        )

        self.source_entry = ctk.CTkEntry(
            self.image_source_frame,
            textvariable=self.source_path,
            height=40,
            border_width=1,
            border_color=self.BORDER,
            fg_color="#FFFFFF",
            text_color=self.TEXT,
            placeholder_text="Path to .img or .dd disk image",
            corner_radius=7,
        )

        self.source_entry.pack(
            side="left",
            fill="x",
            expand=True,
        )

        ctk.CTkButton(
            self.image_source_frame,
            text="Browse",
            width=95,
            height=40,
            fg_color="#FFFFFF",
            hover_color="#F1F5F9",
            border_width=1,
            border_color=self.BORDER,
            text_color=self.TEXT,
            corner_radius=7,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
            command=self._browse_source,
        ).pack(
            side="left",
            padx=(9, 0),
        )

        # -----------------------------------------------------
        # PHYSICAL DEVICE
        # -----------------------------------------------------

        self.device_frame = ctk.CTkFrame(
            source_card,
            fg_color="transparent",
        )

        self.device_combo = ctk.CTkComboBox(
            self.device_frame,
            values=[],
            variable=self.device_path,
            height=40,
            border_width=1,
            border_color=self.BORDER,
            fg_color="#FFFFFF",
            button_color="#E8EEF6",
            button_hover_color="#DCE6F2",
            text_color=self.TEXT,
            corner_radius=7,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
            ),
            dropdown_font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
            ),
            command=self._device_changed,
        )

        self.device_combo.pack(
            side="left",
            fill="x",
            expand=True,
        )

        ctk.CTkButton(
            self.device_frame,
            text="↻  Refresh",
            width=105,
            height=40,
            fg_color="#FFFFFF",
            hover_color="#F1F5F9",
            border_width=1,
            border_color=self.BORDER,
            text_color=self.TEXT,
            corner_radius=7,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
            command=self._refresh_devices,
        ).pack(
            side="left",
            padx=(9, 0),
        )

        self.device_info = ctk.CTkLabel(
            source_card,
            text="",
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
            ),
        )

        # =====================================================
        # OUTPUT CARD
        # =====================================================

        output_card = self._create_card(content)

        output_card.pack(
            fill="x",
            pady=(0, 14),
        )

        ctk.CTkLabel(
            output_card,
            text="RECOVERY OUTPUT",
            text_color=self.TEXT,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=12,
                weight="bold",
            ),
        ).pack(
            anchor="w",
            padx=20,
            pady=(17, 10),
        )

        output_row = ctk.CTkFrame(
            output_card,
            fg_color="transparent",
        )

        output_row.pack(
            fill="x",
            padx=20,
            pady=(0, 17),
        )

        ctk.CTkEntry(
            output_row,
            textvariable=self.output_path,
            height=40,
            border_width=1,
            border_color=self.BORDER,
            fg_color="#FFFFFF",
            text_color=self.TEXT,
            corner_radius=7,
        ).pack(
            side="left",
            fill="x",
            expand=True,
        )

        ctk.CTkButton(
            output_row,
            text="Browse",
            width=95,
            height=40,
            fg_color="#FFFFFF",
            hover_color="#F1F5F9",
            border_width=1,
            border_color=self.BORDER,
            text_color=self.TEXT,
            corner_radius=7,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
            command=self._browse_output,
        ).pack(
            side="left",
            padx=(9, 0),
        )

        # =====================================================
        # ACTIONS
        # =====================================================

        action = ctk.CTkFrame(
            content,
            fg_color="transparent",
        )

        action.pack(
            fill="x",
            pady=(0, 14),
        )

        self.recover_button = ctk.CTkButton(
            action,
            text="START RECOVERY",
            width=190,
            height=46,
            fg_color=self.BLUE,
            hover_color=self.BLUE_HOVER,
            corner_radius=8,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=10,
                weight="bold",
            ),
            command=self._start_recovery,
        )

        self.recover_button.pack(side="left")

        self.open_output_button = ctk.CTkButton(
            action,
            text="Open Output Folder",
            width=160,
            height=46,
            fg_color="#FFFFFF",
            hover_color="#F1F5F9",
            border_width=1,
            border_color=self.BORDER,
            text_color=self.TEXT,
            corner_radius=8,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
            command=self._open_output_folder,
            state="disabled",
        )

        self.open_output_button.pack(
            side="left",
            padx=(10, 0),
        )

        # =====================================================
        # STATUS CARD
        # =====================================================

        status_card = self._create_card(content)

        status_card.pack(
            fill="x",
            pady=(0, 14),
        )

        status_top = ctk.CTkFrame(
            status_card,
            fg_color="transparent",
        )

        status_top.pack(
            fill="x",
            padx=20,
            pady=(17, 8),
        )

        ctk.CTkLabel(
            status_top,
            text="RECOVERY STATUS",
            text_color=self.TEXT,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=12,
                weight="bold",
            ),
        ).pack(side="left")

        self.status_label = ctk.CTkLabel(
            status_top,
            textvariable=self.status_text,
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
        )

        self.status_label.pack(side="right")

        # Progress

        progress_row = ctk.CTkFrame(
            status_card,
            fg_color="transparent",
        )

        progress_row.pack(
            fill="x",
            padx=20,
            pady=(0, 6),
        )

        self.progress = ctk.CTkProgressBar(
            progress_row,
            height=9,
            corner_radius=5,
            fg_color="#E2E8F0",
            progress_color=self.BLUE,
        )

        self.progress.pack(
            side="left",
            fill="x",
            expand=True,
        )

        self.progress.set(0)

        ctk.CTkLabel(
            progress_row,
            textvariable=self.progress_text,
            width=50,
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
                weight="bold",
            ),
        ).pack(
            side="right",
            padx=(12, 0),
        )

        ctk.CTkLabel(
            status_card,
            textvariable=self.status_detail,
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
            ),
        ).pack(
            anchor="w",
            padx=20,
            pady=(0, 13),
        )

        # -----------------------------------------------------
        # METRICS
        # -----------------------------------------------------

        metrics = ctk.CTkFrame(
            status_card,
            fg_color="transparent",
        )

        metrics.pack(
            fill="x",
            padx=20,
            pady=(0, 17),
        )

        self._create_metric(
            metrics,
            "CANDIDATES",
            self.metric_found,
            self.TEXT,
            0,
        )

        self._create_metric(
            metrics,
            "RECOVERED",
            self.metric_recovered,
            self.GREEN,
            1,
        )

        self._create_metric(
            metrics,
            "PARTIAL",
            self.metric_partial,
            self.AMBER,
            2,
        )

        self._create_metric(
            metrics,
            "REJECTED",
            self.metric_rejected,
            self.RED,
            3,
        )

        # =====================================================
        # RESULTS CARD
        # =====================================================

        results_card = self._create_card(content)

        results_card.pack(
            fill="both",
            expand=True,
        )

        result_header = ctk.CTkFrame(
            results_card,
            fg_color="transparent",
        )

        result_header.pack(
            fill="x",
            padx=20,
            pady=(17, 10),
        )

        ctk.CTkLabel(
            result_header,
            text="RECOVERED FILES",
            text_color=self.TEXT,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=12,
                weight="bold",
            ),
        ).pack(side="left")

        ctk.CTkLabel(
            result_header,
            text="Validated recovery artifacts",
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=9,
            ),
        ).pack(side="right")

        # -----------------------------------------------------
        # TABLE
        # -----------------------------------------------------

        table_frame = ctk.CTkFrame(
            results_card,
            fg_color="#FFFFFF",
            corner_radius=7,
            border_width=1,
            border_color=self.BORDER,
        )

        table_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(0, 20),
        )

        columns = (
            "id",
            "type",
            "status",
            "size",
            "confidence",
        )

        self.results = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="ZeroTrace.Treeview",
            selectmode="browse",
        )

        table_columns = {
            "id": ("ID", 125),
            "type": ("TYPE", 90),
            "status": ("STATUS", 190),
            "size": ("SIZE", 130),
            "confidence": ("CONFIDENCE", 120),
        }

        for column, (heading, width) in table_columns.items():

            self.results.heading(
                column,
                text=heading,
            )

            self.results.column(
                column,
                width=width,
                anchor=tk.CENTER,
                stretch=(column == "status"),
            )

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.results.yview,
        )

        self.results.configure(
            yscrollcommand=scrollbar.set,
        )

        self.results.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(1, 0),
            pady=1,
        )

        scrollbar.pack(
            side="right",
            fill="y",
            padx=(0, 1),
            pady=1,
        )

        self.results.tag_configure(
            "reconstructed",
            foreground=self.GREEN,
        )

        self.results.tag_configure(
            "partial",
            foreground=self.AMBER,
        )

        self.results.tag_configure(
            "rejected",
            foreground=self.RED,
        )

    # =========================================================
    # HELPER UI FUNCTIONS
    # =========================================================

    def _create_card(self, parent):

        return ctk.CTkFrame(
            parent,
            fg_color=self.CARD,
            corner_radius=11,
            border_width=1,
            border_color=self.BORDER,
        )

    def _create_metric(
        self,
        parent,
        title,
        variable,
        value_color,
        column,
    ):

        card = ctk.CTkFrame(
            parent,
            fg_color="#F8FAFC",
            corner_radius=8,
            border_width=1,
            border_color=self.BORDER,
        )

        card.grid(
            row=0,
            column=column,
            sticky="ew",
            padx=(0 if column == 0 else 6, 0),
        )

        parent.grid_columnconfigure(
            column,
            weight=1,
        )

        ctk.CTkLabel(
            card,
            text=title,
            text_color=self.MUTED,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=8,
                weight="bold",
            ),
        ).pack(
            anchor="w",
            padx=13,
            pady=(10, 0),
        )

        ctk.CTkLabel(
            card,
            textvariable=variable,
            text_color=value_color,
            font=ctk.CTkFont(
                family="Segoe UI",
                size=20,
                weight="bold",
            ),
        ).pack(
            anchor="w",
            padx=13,
            pady=(0, 9),
        )

    # =========================================================
    # SOURCE MODE
    # =========================================================

    def _change_source_mode(self, value: str) -> None:

        if value == "Physical Drive":
            self.source_mode.set("physical")
        else:
            self.source_mode.set("image")

        self._update_source_mode()

    def _update_source_mode(self) -> None:

        if self.source_mode.get() == "physical":

            self.image_source_frame.pack_forget()

            self.device_frame.pack(
                fill="x",
                padx=20,
                pady=(0, 6),
            )

            self.device_info.pack(
                anchor="w",
                padx=20,
                pady=(0, 12),
            )

            self.source_badge.configure(
                text="PHYSICAL DRIVE",
                text_color=self.GREEN,
                fg_color=self.GREEN_LIGHT,
            )

            self.source_description.configure(
                text=(
                    "Select a physical HDD, SSD, USB drive, "
                    "or other exposed storage device."
                )
            )

            self._refresh_devices()

        else:

            self.device_frame.pack_forget()
            self.device_info.pack_forget()

            self.image_source_frame.pack(
                fill="x",
                padx=20,
                pady=(0, 12),
            )

            self.source_badge.configure(
                text="DISK IMAGE",
                text_color=self.BLUE,
                fg_color=self.BLUE_LIGHT,
            )

            self.source_description.configure(
                text=(
                    "Select a disk image (.img or .dd) "
                    "as the recovery source."
                )
            )

    # =========================================================
    # PHYSICAL DEVICES
    # =========================================================

    def _refresh_devices(self) -> None:

        try:

            self.devices = enumerate_physical_devices()

        except Exception as exc:

            self.devices = []

            self.device_path.set("")

            self.device_combo.configure(
                values=[]
            )

            self.device_combo.set("")

            self.device_info.configure(
                text=f"Unable to enumerate devices: {exc}"
            )

            return

        values = []

        for device in self.devices:

            values.append(
                f"{device.path}  •  "
                f"{device.model}  •  "
                f"{device.capacity_label}  •  "
                f"{device.media_type}"
            )

        self.device_combo.configure(
            values=values
        )

        if self.devices:

            self.device_combo.set(
                values[0]
            )

            self.device_path.set(
                self.devices[0].path
            )

            self.device_info.configure(
                text=(
                    f"Selected: "
                    f"{self.devices[0].model}  |  "
                    f"{self.devices[0].capacity_label}  |  "
                    f"{self.devices[0].media_type}  |  "
                    f"READ-ONLY"
                )
            )

        else:

            self.device_combo.set("")
            self.device_path.set("")

            self.device_info.configure(
                text="No physical storage devices were available."
            )

    def _device_changed(self, value: str) -> None:

        if not self.devices:
            return

        for device in self.devices:

            label = (
                f"{device.path}  •  "
                f"{device.model}  •  "
                f"{device.capacity_label}  •  "
                f"{device.media_type}"
            )

            if value == label:

                self.device_path.set(
                    device.path
                )

                self.device_info.configure(
                    text=(
                        f"Selected: "
                        f"{device.model}  |  "
                        f"{device.capacity_label}  |  "
                        f"{device.media_type}  |  "
                        f"READ-ONLY"
                    )
                )

                break

    # =========================================================
    # FILE DIALOGS
    # =========================================================

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
            title="Select Recovery Output Directory"
        )

        if path:
            self.output_path.set(path)

    # =========================================================
    # RECOVERY
    # =========================================================

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

        # -----------------------------------------------------
        # PHYSICAL DEVICE
        # -----------------------------------------------------

        if self.source_mode.get() == "physical":

            try:

                validate_output_destination(
                    source,
                    output,
                )

                reader_factory = physical_reader_factory(
                    source
                )

            except (OSError, ValueError) as exc:

                messagebox.showerror(
                    "Invalid Physical Device",
                    str(exc),
                )

                return

        # -----------------------------------------------------
        # DISK IMAGE
        # -----------------------------------------------------

        else:

            if (
                not source_path.exists()
                or not source_path.is_file()
            ):

                messagebox.showerror(
                    "Invalid Source",
                    (
                        "The selected source is not "
                        "a readable file:\n\n"
                        f"{source}"
                    ),
                )

                return

        # -----------------------------------------------------
        # RESET UI
        # -----------------------------------------------------

        self._clear_results()
        self._reset_metrics()

        self.recover_button.configure(
            state="disabled"
        )

        self.open_output_button.configure(
            state="disabled"
        )

        self.status_text.set(
            "Scanning"
        )

        self.status_detail.set(
            "Analyzing raw source data and validating recovery candidates."
        )

        self.progress_text.set(
            "Scanning"
        )

        self.progress.configure(
            progress_color=self.BLUE
        )

        self.progress.start()

        # -----------------------------------------------------
        # WORKER THREAD
        # -----------------------------------------------------

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

    # =========================================================
    # RESULTS
    # =========================================================

    def _show_results(self, result) -> None:

        self.progress.stop()

        self.progress.set(1)

        self.progress_text.set(
            "100%"
        )

        self.recover_button.configure(
            state="normal"
        )

        self.last_output_path = Path(
            result.output_dir
        )

        if (
            self.last_output_path.exists()
            and self.last_output_path.is_dir()
        ):

            self.open_output_button.configure(
                state="normal"
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

        # -----------------------------------------------------
        # METRICS
        # -----------------------------------------------------

        self.metric_found.set(
            str(result.candidates_found)
        )

        self.metric_recovered.set(
            str(recovered)
        )

        self.metric_partial.set(
            str(partial)
        )

        self.metric_rejected.set(
            str(rejected)
        )

        # -----------------------------------------------------
        # TABLE
        # -----------------------------------------------------

        for artifact in result.recovered_files:

            status = str(
                artifact.status
            )

            tag = {
                "RECONSTRUCTED": "reconstructed",
                "PARTIAL": "partial",
                "REJECTED": "rejected",
            }.get(
                status,
                "",
            )

            self.results.insert(
                "",
                tk.END,
                values=(
                    artifact.recovery_id,
                    artifact.file_type,
                    status,
                    f"{artifact.size} bytes",
                    f"{artifact.confidence:.3f}",
                ),
                tags=(tag,),
            )

        # -----------------------------------------------------
        # STATUS
        # -----------------------------------------------------

        self.status_text.set(
            "Recovery complete"
        )

        self.status_detail.set(
            f"{recovered} recovered  •  "
            f"{partial} partial  •  "
            f"{rejected} rejected  •  "
            f"{result.candidates_found} candidates"
        )

        # -----------------------------------------------------
        # MESSAGE
        # -----------------------------------------------------

        if result.errors:

            messagebox.showwarning(
                "Recovery Completed with Errors",
                "\n".join(
                    result.errors
                ),
            )

        elif result.warnings:

            messagebox.showinfo(
                "Recovery Completed",
                (
                    "Recovery finished with warnings.\n\n"
                    f"Found: {result.candidates_found}\n"
                    f"Recovered: {recovered}\n"
                    f"Partial: {partial}\n"
                    f"Rejected: {rejected}\n\n"
                    f"Output: {result.output_dir}"
                ),
            )

        else:

            messagebox.showinfo(
                "Recovery Completed",
                (
                    "Recovery completed successfully.\n\n"
                    f"Found: {result.candidates_found}\n"
                    f"Recovered: {recovered}\n"
                    f"Partial: {partial}\n"
                    f"Rejected: {rejected}\n\n"
                    f"Output: {result.output_dir}"
                ),
            )

    # =========================================================
    # ERROR
    # =========================================================

    def _show_error(
        self,
        exc: Exception,
    ) -> None:

        self.progress.stop()

        self.progress.set(0)

        self.progress_text.set(
            "Error"
        )

        self.recover_button.configure(
            state="normal"
        )

        self.status_text.set(
            "Recovery failed"
        )

        self.status_detail.set(
            str(exc)
        )

        messagebox.showerror(
            "Recovery Error",
            str(exc),
        )

    # =========================================================
    # UTILITY
    # =========================================================

    def _reset_metrics(self) -> None:

        self.metric_found.set("0")
        self.metric_recovered.set("0")
        self.metric_partial.set("0")
        self.metric_rejected.set("0")

    def _clear_results(self) -> None:

        for item in self.results.get_children():

            self.results.delete(
                item
            )

    def _open_output_folder(self) -> None:

        if self.last_output_path is None:
            return

        if not self.last_output_path.exists():

            messagebox.showerror(
                "Output Not Found",
                (
                    "The output directory does not exist:\n\n"
                    f"{self.last_output_path}"
                ),
            )

            return

        try:

            os.startfile(
                self.last_output_path
            )

        except OSError as exc:

            messagebox.showerror(
                "Unable to Open Folder",
                str(exc),
            )


# =============================================================
# MAIN
# =============================================================

def main() -> None:

    root = ctk.CTk()

    DriveRecoveryGUI(
        root
    )

    root.mainloop()


if __name__ == "__main__":

    main()