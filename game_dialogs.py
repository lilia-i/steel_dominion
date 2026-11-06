import tkinter as tk
from tkinter import ttk

from game_config import ENEMY, NEUTRAL, PLAYER, UNIT_TYPES
from unit_effects import get_unit_skills, get_unit_statuses
from ui_helpers import ScrollableFrame


INK = "#202c27"
MUTED = "#768078"
PAPER = "#e8e7df"
GREEN = "#47745f"


def _show_effect_info(parent, effect):
    EffectInfoDialog(parent.winfo_toplevel(), effect)


def _effect_icon(parent, effect):
    icon = tk.Label(parent, text=effect.icon, width=2, bg=PAPER, fg=INK,
                    font=("Segoe UI", 10, "bold"), cursor="hand2", bd=0,
                    takefocus=True)
    icon.bind("<Button-1>", lambda event: _show_effect_info(parent, effect))
    icon.bind("<Return>", lambda event: _show_effect_info(parent, effect))
    icon.bind("<Enter>", lambda event: icon.configure(fg=GREEN))
    icon.bind("<Leave>", lambda event: icon.configure(fg=INK))
    return icon


class _ModalDialog(tk.Frame):
    def __init__(self, parent, title, width, height):
        tk.Frame.__init__(self, parent, bg=PAPER, highlightthickness=1,
                          highlightbackground="#c9cec4", bd=0)
        self.parent = parent
        self.dialog_title = title
        self._size = (width, height)
        self.previous_grab = None

    def _show_modal(self):
        self.previous_grab = self.grab_current()
        self.update_idletasks()
        width, height = self._size
        self.place(relx=0.5, rely=0.5, anchor="center",
                   width=width, height=height)
        self.lift()
        self.grab_set()

    def _build_header(self, title, subtitle=None, eyebrow=None):
        header = tk.Frame(self, bg=INK, padx=20, pady=14)
        header.pack(fill="x")
        title_row = tk.Frame(header, bg=INK)
        title_row.pack(fill="x")
        title_text = tk.Frame(title_row, bg=INK)
        title_text.pack(side="left", fill="x", expand=True)
        if eyebrow:
            tk.Label(title_text, text=eyebrow.upper(), bg=INK, fg="#a9b3a9",
                     font=("Consolas", 8, "bold")).pack(anchor="w")
        tk.Label(title_text, text=title, bg=INK, fg="#f5f2e8",
                 font=("Georgia", 16, "bold")).pack(anchor="w", pady=(3, 0))
        tk.Button(title_row, text="X", command=self.close, bg=INK, fg="#f5f2e8",
                  activebackground="#365b49", activeforeground="white",
                  relief="flat", bd=0, padx=8, font=("Segoe UI", 10, "bold"),
                  cursor="hand2").pack(side="right", anchor="n")
        if subtitle:
            tk.Label(header, text=subtitle, bg=INK, fg="#c4cbc1",
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 0))

    def close(self):
        previous_grab = self.previous_grab
        try:
            if self.grab_current() == self:
                self.grab_release()
        except tk.TclError:
            pass
        self.place_forget()
        tk.Frame.destroy(self)
        if previous_grab:
            try:
                if previous_grab.winfo_exists():
                    previous_grab.grab_set()
            except tk.TclError:
                pass


class EffectInfoDialog(_ModalDialog):
    def __init__(self, parent, effect):
        _ModalDialog.__init__(self, parent, effect.name, 420, 230)
        self._build_header(effect.name)
        content = ttk.Frame(self, padding=20)
        content.pack(fill="both", expand=True)
        ttk.Label(content, text=effect.description, wraplength=370,
                  justify="left").pack(anchor="w")
        self._show_modal()


class CountryChoiceDialog(_ModalDialog):
    def __init__(self, parent, model, country_id, on_confirm):
        self.on_confirm = on_confirm
        self.country_id = country_id
        country_name = model.country_name(country_id)
        _ModalDialog.__init__(self, parent, "Choose country", 430, 250)
        self._build_header(country_name, "Begin the campaign as this country?")
        content = ttk.Frame(self, padding=(20, 12, 20, 10))
        content.pack(fill="both", expand=True)
        ttk.Label(content, text="Confirm this country for your campaign.",
                  wraplength=370).pack(anchor="w")
        actions = ttk.Frame(content)
        actions.pack(side="bottom", fill="x", pady=(16, 0))
        ttk.Button(actions, text="Cancel", command=self.close).pack(side="right")
        ttk.Button(actions, text="Choose country", style="Accent.TButton",
                   command=self._confirm).pack(side="right", padx=(0, 8))
        self._show_modal()

    def _confirm(self):
        country_id = self.country_id
        callback = self.on_confirm
        self.close()
        callback(country_id)

class UnitInfoDialog(_ModalDialog):
    def __init__(self, parent, model, unit, debug_mode=False):
        name = "Transport ship ({})".format(unit.kind) if unit.embarked else unit.kind
        owner_name = model.country_name(unit.owner)
        faction = model.faction_for(unit.owner)
        faction_name = {PLAYER: "Player faction", ENEMY: "Enemy faction",
                        NEUTRAL: "Neutral"}.get(faction, faction)
        _ModalDialog.__init__(self, parent, "Unit details", 600, 370)
        self._build_header(name, "{}  /  {}".format(owner_name, faction_name))

        content = ttk.Frame(self, padding=(18, 14, 18, 8))
        content.pack(fill="both", expand=True)
        rows = (
            ("ATTACK", "{:g}".format(unit.effective_attack)),
            ("RANGE", "{} hex".format(unit.range)),
            ("STRENGTH", "{}/{} HP".format(unit.hp, unit.max_hp)),
            ("MOVEMENT", "{} MP".format(unit.movement)),
            ("ATTACKS", "{}/{}".format(unit.attacks_left, unit.attacks_per_turn)),
        )
        if debug_mode:
            rows += (("BASE ATTACK", str(unit.attack)),)
        profile = ttk.LabelFrame(content, text="COMBAT PROFILE", padding=(10, 8))
        profile.pack(side="left", fill="both", expand=True)
        for index, (label, value) in enumerate(rows):
            cell = ttk.Frame(profile, padding=(8, 10))
            cell.grid(row=index // 3, column=index % 3, sticky="nsew",
                      padx=3, pady=3)
            ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
            ttk.Label(cell, text=value,
                      font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(5, 0))
        for column in range(3):
            profile.columnconfigure(column, weight=1)
        profile.rowconfigure(0, weight=1)
        profile.rowconfigure(1, weight=1)
        effects = ttk.Frame(profile)
        effects.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        for skill in get_unit_skills(unit):
            _effect_icon(effects, skill).pack(side="left", padx=(0, 4))
        for status in get_unit_statuses(unit):
            _effect_icon(effects, status).pack(side="left", padx=(0, 4))

        self._show_modal()


class RecruitDialog(_ModalDialog):
    def __init__(self, parent, model, city, player_country_id,
                 campaign_started, on_recruit):
        _ModalDialog.__init__(self, parent, "Recruit units", 600, 400)
        self.model = model
        self.city = city
        self.player_country_id = player_country_id
        self.campaign_started = campaign_started
        self.on_recruit = on_recruit
        self.kind_var = tk.StringVar(value=next(iter(UNIT_TYPES)))
        self.resources = model.countries[city["owner"]]["resources"]
        self.status_var = tk.StringVar()

        owner = model.country_name(city["owner"])
        self._build_header(city["name"],
                   "{}  /  City Lv {}".format(owner, city["city_level"]))

        content = ttk.Frame(self, padding=(12, 7, 12, 4))
        content.pack(fill="both", expand=True)
        selection = ttk.Frame(content, padding=(4, 2))
        selection.pack(fill="both", expand=True)
        selection.columnconfigure(0, weight=4)
        for column in range(1, 5):
            selection.columnconfigure(column, weight=1, uniform="recruit-stats",
                                     minsize=54)
        self.kind_labels = {}
        self.kind_rows = {}
        for column, label in enumerate(("UNIT / COST", "ATTACK", "RANGE", "HP", "MOVE")):
            ttk.Label(selection, text=label, style="Muted.TLabel").grid(
                row=0, column=column, sticky="w" if column == 0 else "",
                padx=(4, 0) if column == 0 else 0, pady=(0, 4))

        for index, (kind, details) in enumerate(UNIT_TYPES.items()):
            row = 1 + index * 2
            cost = details["cost"]
            row_panel = ttk.Frame(selection, padding=(4, 3))
            row_panel.grid(row=row, column=0, columnspan=5, sticky="ew",
                           pady=(1, 1))
            row_panel.columnconfigure(0, weight=4)
            for column in range(1, 5):
                row_panel.columnconfigure(column, weight=1,
                                          uniform="recruit-row-stats",
                                          minsize=54)
            row_panel.bind("<Button-1>",
                           lambda event, selected_kind=kind:
                           self._select_kind(selected_kind))
            self.kind_rows[kind] = row_panel

            unit_choice = ttk.Frame(row_panel)
            unit_choice.grid(row=0, column=0, sticky="w")
            unit_choice.bind("<Button-1>",
                             lambda event, selected_kind=kind:
                             self._select_kind(selected_kind))
            kind_label = ttk.Label(unit_choice, text=kind, cursor="hand2")
            kind_label.pack(side="left")
            kind_label.bind("<Button-1>",
                            lambda event, selected_kind=kind:
                            self._select_kind(selected_kind))
            self.kind_labels[kind] = kind_label
            for skill in get_unit_skills(kind):
                _effect_icon(unit_choice, skill).pack(side="left", padx=(5, 0))
            cost_text = "Cost  Money {}  /  Steel {}  /  Tech {}".format(
                cost["money"], cost["steel"], cost["technology"])
            cost_label = ttk.Label(row_panel, text=cost_text, style="Muted.TLabel",
                                   cursor="hand2")
            cost_label.grid(row=1, column=0, sticky="ew", padx=(24, 0),
                            pady=(1, 0))
            cost_label.bind("<Button-1>",
                            lambda event, selected_kind=kind:
                            self._select_kind(selected_kind))
            values = (details["attack"], details["range"], details["hp"],
                      details["movement"])
            for column, value in enumerate(values, start=1):
                value_label = ttk.Label(row_panel, text=str(value),
                                        font=("Segoe UI", 11, "bold"),
                                        cursor="hand2")
                value_label.grid(row=0, column=column, rowspan=2,
                                 sticky="nsew", pady=(3, 0))
                value_label.bind("<Button-1>",
                                 lambda event, selected_kind=kind:
                                 self._select_kind(selected_kind))
            if index < len(UNIT_TYPES) - 1:
                ttk.Separator(selection).grid(row=row + 1, column=0, columnspan=5,
                                              sticky="ew", pady=(2, 0))

        ttk.Label(content, textvariable=self.status_var, wraplength=700,
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 2))

        footer = ttk.Frame(self, padding=(18, 6, 18, 10))
        footer.pack(fill="x")
        self.recruit_button = ttk.Button(
            footer, text="Recruit", style="Accent.TButton", command=self._recruit)
        self.recruit_button.pack(side="right", padx=(0, 8))

        self._refresh_preview()
        self._show_modal()

    def _refresh_preview(self):
        kind = self.kind_var.get()
        for unit_kind, label in self.kind_labels.items():
            label.configure(foreground=GREEN if unit_kind == kind else INK,
                            font=("Segoe UI", 9,
                                  "bold" if unit_kind == kind else "normal"))
        details = UNIT_TYPES[kind]
        cost = details["cost"]
        if not self.campaign_started:
            reason = "Start the campaign before recruiting units."
        elif self.model.phase != PLAYER:
            reason = "Recruitment is available during the player turn."
        elif self.city["owner"] != self.player_country_id:
            reason = "You can only recruit from your own cities."
        else:
            missing = [resource for resource, amount in cost.items()
                       if self.resources[resource] < amount]
            if missing:
                reason = "Insufficient resources: {}.".format(
                    ", ".join(missing).title())
            else:
                city_available = self.model.unit_at(self.city["position"]) is None
                reason = ("The city must be empty to recruit a unit."
                          if not city_available else
                          "Ready to deploy at {}.".format(self.city["name"]))

        can_recruit = reason.startswith("Ready to deploy")
        self.status_var.set(reason)
        self.recruit_button.configure(
            text="Recruit {}".format(kind),
            state="normal" if can_recruit else "disabled")

    def _select_kind(self, kind):
        self.kind_var.set(kind)
        self._refresh_preview()

    def _recruit(self):
        unit, message = self.model.recruit(self.city["position"], self.kind_var.get())
        if unit:
            self.on_recruit(unit, message)
            self.close()
            return
        self.status_var.set(message)


class SettingsDialog(_ModalDialog):
    def __init__(self, parent, model, player_country_id, pending_country_id,
                 resource_country_id, campaign_started, current_map_name,
                 history, debug_mode, attack_target,
                 on_resource_selected, on_choose_map, on_campaign_action,
                 on_change_country, on_attack, on_cancel_attack, on_debug_changed):
        _ModalDialog.__init__(self, parent, "Campaign settings", 520, 390)
        self.model = model
        self.player_country_id = player_country_id
        self.pending_country_id = pending_country_id
        self.resource_country_id = resource_country_id
        self.campaign_started = campaign_started
        self.on_resource_selected = on_resource_selected
        self.on_choose_map = on_choose_map
        self.on_campaign_action = on_campaign_action
        self.on_change_country = on_change_country
        self.on_attack = on_attack
        self.on_cancel_attack = on_cancel_attack
        self.on_debug_changed = on_debug_changed
        self.resource_country_var = tk.StringVar()
        self.debug_var = tk.BooleanVar(value=debug_mode)
        self.turn_var = tk.StringVar(value=str(model.turn))
        self.phase_var = tk.StringVar()
        self.city_count_var = tk.StringVar()
        self.map_var = tk.StringVar(value=current_map_name)

        phase = ("Campaign setup" if not campaign_started else
                 "Player turn" if model.phase == PLAYER else
                 "AI turn" if model.phase == ENEMY else "Campaign complete")
        self.phase_var.set(phase)
        selected_country_id = (player_country_id if campaign_started else
                               pending_country_id)
        cities = model.owned_cities(selected_country_id)
        self.city_count_var.set("{} / {} controlled".format(cities, len(model.cities)))
        self._build_header("Settings")

        self.scrollable = ScrollableFrame(self, canvas_bg=PAPER)
        self.scrollable.pack(fill="both", expand=True)
        content = ttk.Frame(self.scrollable.content, padding=(16, 10, 16, 12))
        content.pack(fill="both", expand=True)

        self.debug_summary = ttk.LabelFrame(
            content, text="CAMPAIGN DETAILS", padding=(10, 7))
        for column, label, variable in (
                (0, "MAP", self.map_var), (1, "TURN", self.turn_var),
                (2, "STATUS", self.phase_var), (3, "CITIES", self.city_count_var)):
            cell = ttk.Frame(self.debug_summary)
            cell.grid(row=0, column=column, sticky="nw", padx=5, pady=2)
            ttk.Label(cell, text=label, style="Muted.TLabel").pack(anchor="w")
            ttk.Label(cell, textvariable=variable,
                      font=("Segoe UI", 9, "bold"), wraplength=105).pack(
                          anchor="w", pady=(3, 0))
            self.debug_summary.columnconfigure(column, weight=1)

        selectors = ttk.Frame(content)
        selectors.pack(fill="x")
        self.resource_label = ttk.Label(selectors, text="Resource account")
        self.resource_label.pack(anchor="w")
        self.resource_country_choice = ttk.Combobox(
            selectors, textvariable=self.resource_country_var, state="readonly")
        self.resource_country_choice.pack(fill="x", pady=(2, 0))
        self.resource_country_choice.bind("<<ComboboxSelected>>", self._select_resource_country)
        self._update_resource_accounts()

        self.debug_toggle = ttk.Checkbutton(
            content, text="Debug mode", variable=self.debug_var,
            command=self._toggle_debug)
        self.debug_toggle.pack(anchor="w", pady=(6, 8))

        self.actions = ttk.Frame(content)
        self.actions.pack(fill="x")
        ttk.Button(self.actions, text="Choose map", command=self._choose_map).pack(
            fill="x", pady=(0, 4))
        if campaign_started:
            ttk.Button(self.actions, text="Restart campaign",
                       command=self._campaign_action).pack(fill="x", pady=(0, 4))
            ttk.Button(self.actions, text="Change country", command=self._change_country).pack(
                fill="x", pady=(0, 4))
        if attack_target is not None:
            ttk.Button(self.actions, text="Attack target", style="Accent.TButton",
                       command=self._attack).pack(fill="x", pady=(0, 4))
            ttk.Button(self.actions, text="Clear target", command=self._clear_target).pack(
                fill="x")

        report = ttk.LabelFrame(content, text="FIELD REPORT", padding=8)
        self.debug_report = report
        self.log_box = tk.Listbox(report, height=5, borderwidth=0,
                                  highlightthickness=0, bg="#f4f3ed", fg="#46534b",
                                  font=("Segoe UI", 9), activestyle="none")
        self.log_box.pack(fill="both", expand=True)
        for entry in history[:20]:
            self.log_box.insert(tk.END, entry)

        self._apply_debug_visibility()
        self._show_modal()

    def _update_resource_accounts(self):
        country_id = (self.player_country_id if self.campaign_started else
                      self.pending_country_id)
        faction = self.model.faction_for(country_id)
        countries = [country for country in self.model.countries.values()
                     if country["faction"] == faction]
        self.resource_country_ids = [country["id"] for country in countries]
        self.resource_country_choice.configure(
            values=[country["name"] for country in countries],
            state="readonly" if self.campaign_started else "disabled")
        if self.resource_country_id not in self.resource_country_ids:
            self.resource_country_id = country_id
        self.resource_country_var.set(self.model.country_name(self.resource_country_id))

    def _select_resource_country(self, event=None):
        selected_name = self.resource_country_var.get()
        country_id = next((country_id for country_id in self.resource_country_ids
                           if self.model.country_name(country_id) == selected_name), None)
        if country_id is not None:
            self.resource_country_id = country_id
            self.on_resource_selected(country_id)

    def _toggle_debug(self):
        self._apply_debug_visibility()
        self.on_debug_changed(self.debug_var.get())

    def _apply_debug_visibility(self):
        if self.debug_var.get():
            if not self.resource_label.winfo_manager():
                self.resource_label.pack(anchor="w")
                self.resource_country_choice.pack(fill="x", pady=(2, 0))
            if not self.debug_summary.winfo_manager():
                self.debug_summary.pack(fill="x", pady=(0, 8), before=self.actions)
            if not self.debug_report.winfo_manager():
                self.debug_report.pack(fill="both", expand=True, pady=(8, 0))
        else:
            self.resource_label.pack_forget()
            self.resource_country_choice.pack_forget()
            self.debug_summary.pack_forget()
            self.debug_report.pack_forget()
        self.scrollable._update_scroll_region()

    def _choose_map(self):
        self.close()
        self.on_choose_map()

    def _campaign_action(self):
        self.close()
        self.on_campaign_action()

    def _change_country(self):
        self.close()
        self.on_change_country()

    def _attack(self):
        self.close()
        self.on_attack()

    def _clear_target(self):
        self.close()
        self.on_cancel_attack()