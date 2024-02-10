import tkinter as tk
from functools import partial
from os import path
from tkinter import PhotoImage, ttk

from ttkHyperlinkLabel import HyperlinkLabel

from bgstally.activity import STATES_WAR, Activity
from bgstally.constants import COLOUR_HEADING_1, FOLDER_ASSETS, FONT_HEADING_1, FONT_HEADING_2, FONT_TEXT, CheckStates, CZs, DiscordActivity, DiscordChannel, DiscordPostStyle
from bgstally.debug import Debug
from bgstally.utils import human_format
from bgstally.widgets import DiscordAnsiColorText, TextPlus
from thirdparty.colors import *
from thirdparty.ScrollableNotebook import ScrollableNotebook

LIMIT_TABS = 60


class WindowActivity:
    """
    Handles an activity window
    """

    def __init__(self, bgstally, ui, activity: Activity):
        self.bgstally = bgstally
        self.ui = ui
        self.activity:Activity = activity
        self.toplevel:tk.Toplevel = None
        self.window_geometry:dict = None

        self.image_tab_active_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_active_enabled.png"))
        self.image_tab_active_part_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_active_part_enabled.png"))
        self.image_tab_active_disabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_active_disabled.png"))
        self.image_tab_inactive_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_inactive_enabled.png"))
        self.image_tab_inactive_part_enabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_inactive_part_enabled.png"))
        self.image_tab_inactive_disabled = PhotoImage(file = path.join(self.bgstally.plugin_dir, FOLDER_ASSETS, "tab_inactive_disabled.png"))

        self.show(activity)


    def show(self, activity: Activity):
        """
        Show our window
        """
        # If we already have a window, save its geometry and close it before we create a new one.
        if self.toplevel is not None and self.toplevel.winfo_exists():
            self._store_window_geometry()
            self.toplevel.destroy()

        self.toplevel = tk.Toplevel(self.ui.frame)
        self.toplevel.protocol("WM_DELETE_WINDOW", self._window_closed)

        if self.window_geometry is not None:
            self.toplevel.geometry(f"{self.window_geometry['w']}x{self.window_geometry['h']}+{self.window_geometry['x']}+{self.window_geometry['y']}")

        self.toplevel.title(f"{self.bgstally.plugin_name} - Activity After Tick at: {activity.get_title()}")

        ContainerFrame = ttk.Frame(self.toplevel)
        ContainerFrame.pack(fill=tk.BOTH, expand=tk.YES)
        TabParent=ScrollableNotebook(ContainerFrame, wheelscroll=False, tabmenu=True)
        TabParent.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)

        frame_buttons:ttk.Frame = ttk.Frame(ContainerFrame)
        frame_buttons.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(frame_buttons, text="Copy to Clipboard (Legacy Format)", command=partial(self._copy_to_clipboard, ContainerFrame, activity)).pack(side=tk.LEFT, padx=5, pady=5)
        self.btn_post_to_discord: ttk.Button = ttk.Button(frame_buttons, text="Post to Discord", command=partial(self._post_to_discord, activity),
                                                          state=('normal' if self._discord_button_available() else 'disabled'))
        self.btn_post_to_discord.pack(side=tk.RIGHT, padx=5, pady=5)

        DiscordFrame = ttk.Frame(ContainerFrame)
        DiscordFrame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        DiscordFrame.columnconfigure(0, weight=2)
        DiscordFrame.columnconfigure(1, weight=1)
        label_discord_report:ttk.Label = ttk.Label(DiscordFrame, text="❓ Discord Report Preview", font=FONT_HEADING_2, cursor="hand2")
        label_discord_report.grid(row=0, column=0, sticky=tk.W)
        label_discord_report.bind("<Button-1>", self._show_legend_window)
        ttk.Label(DiscordFrame, text="Discord Additional Notes", font=FONT_HEADING_2).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(DiscordFrame, text="Discord Options", font=FONT_HEADING_2).grid(row=0, column=2, sticky=tk.W)
        ttk.Label(DiscordFrame, text="Double-check on-ground CZ tallies, sizes are not always correct", foreground='#f00').grid(row=1, column=0, columnspan=3, sticky=tk.W)

        DiscordTextFrame = ttk.Frame(DiscordFrame)
        DiscordTextFrame.grid(row=2, column=0, pady=5, sticky=tk.NSEW)
        DiscordText = DiscordAnsiColorText(DiscordTextFrame, state='disabled', wrap=tk.WORD, bg="Gray13", height=15, font=FONT_TEXT)
        DiscordScroll = tk.Scrollbar(DiscordTextFrame, orient=tk.VERTICAL, command=DiscordText.yview)
        DiscordText['yscrollcommand'] = DiscordScroll.set
        DiscordScroll.pack(fill=tk.Y, side=tk.RIGHT)
        DiscordText.pack(fill=tk.BOTH, side=tk.LEFT, expand=tk.YES)

        DiscordNotesFrame = ttk.Frame(DiscordFrame)
        DiscordNotesFrame.grid(row=2, column=1, pady=5, sticky=tk.NSEW)
        DiscordNotesText = TextPlus(DiscordNotesFrame, wrap=tk.WORD, width=30, height=1, font=FONT_TEXT)
        DiscordNotesText.insert(tk.END, "" if activity.discord_notes is None else activity.discord_notes)
        DiscordNotesText.bind("<<Modified>>", partial(self._discord_notes_change, DiscordNotesText, DiscordText, activity))
        DiscordNotesScroll = tk.Scrollbar(DiscordNotesFrame, orient=tk.VERTICAL, command=DiscordNotesText.yview)
        DiscordNotesText['yscrollcommand'] = DiscordNotesScroll.set
        DiscordNotesScroll.pack(fill=tk.Y, side=tk.RIGHT)
        DiscordNotesText.pack(fill=tk.BOTH, side=tk.LEFT, expand=tk.YES)

        DiscordOptionsFrame = ttk.Frame(DiscordFrame)
        DiscordOptionsFrame.grid(row=2, column=2, padx=5, pady=5, sticky=tk.NW)
        current_row = 1
        ttk.Label(DiscordOptionsFrame, text="Post Format").grid(row=current_row, column=0, padx=10, sticky=tk.W)
        ttk.Radiobutton(DiscordOptionsFrame, text="Modern", variable=self.bgstally.state.DiscordPostStyle, value=DiscordPostStyle.EMBED).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1
        ttk.Radiobutton(DiscordOptionsFrame, text="Legacy", variable=self.bgstally.state.DiscordPostStyle, value=DiscordPostStyle.TEXT).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1
        ttk.Label(DiscordOptionsFrame, text="Other Options").grid(row=current_row, column=0, padx=10, sticky=tk.W)
        ttk.Checkbutton(DiscordOptionsFrame, text="Abbreviate Faction Names", variable=self.bgstally.state.AbbreviateFactionNames, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=partial(self._option_change, DiscordText, activity)).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1
        ttk.Checkbutton(DiscordOptionsFrame, text="Show Detailed INF", variable=self.bgstally.state.DetailedInf, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=partial(self._option_change, DiscordText, activity)).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1
        ttk.Checkbutton(DiscordOptionsFrame, text="Include Secondary INF", variable=self.bgstally.state.IncludeSecondaryInf, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=partial(self._option_change, DiscordText, activity)).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1
        ttk.Checkbutton(DiscordOptionsFrame, text="Show Detailed Trade", variable=self.bgstally.state.DetailedTrade, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF, command=partial(self._option_change, DiscordText, activity)).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1
        ttk.Checkbutton(DiscordOptionsFrame, text="Report Newly Visited System Activity By Default", variable=self.bgstally.state.EnableSystemActivityByDefault, onvalue=CheckStates.STATE_ON, offvalue=CheckStates.STATE_OFF).grid(row=current_row, column=1, padx=10, sticky=tk.W); current_row += 1

        system_list = activity.get_ordered_systems()

        tab_index = 0

        for system_id in system_list:
            if tab_index > LIMIT_TABS: # If we try to draw too many, the plugin simply hangs
                Debug.logger.warn(f"Window tab limit ({LIMIT_TABS}) exceeded, skipping remaining tabs")
                break

            system = activity.systems[system_id]

            if self.bgstally.state.ShowZeroActivitySystems.get() == CheckStates.STATE_OFF \
                and system['zero_system_activity'] \
                and str(system_id) != self.bgstally.state.current_system_id: continue

            tab:ttk.Frame = ttk.Frame(TabParent)
            TabParent.add(tab, text=system['System'], compound='right', image=self.image_tab_active_enabled)

            frame_header:ttk.Frame = ttk.Frame(tab)
            frame_header.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)
            ttk.Label(frame_header, text=system['System'], font=FONT_HEADING_1, foreground=COLOUR_HEADING_1).grid(row=0, column=0, padx=2, pady=2)

            HyperlinkLabel(frame_header, text="Inara ⤴", url=f"https://inara.cz/elite/starsystem/?search={system['System']}", underline=True).grid(row=0, column=1, padx=2, pady=2)

            frame_table:ttk.Frame = ttk.Frame(tab)
            frame_table.pack(fill=tk.BOTH, side=tk.TOP, padx=5, pady=5, expand=tk.YES)
            frame_table.columnconfigure(1, weight=1) # Make the second column (faction name) fill available space

            FactionEnableCheckbuttons = []

            ttk.Label(frame_table, text="Include", font=FONT_HEADING_2).grid(row=0, column=0, padx=2, pady=2)
            EnableAllCheckbutton = ttk.Checkbutton(frame_table)
            EnableAllCheckbutton.grid(row=1, column=0, padx=2, pady=2)
            EnableAllCheckbutton.configure(command=partial(self._enable_all_factions_change, TabParent, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system))
            EnableAllCheckbutton.state(['!alternate'])

            col: int = 1
            ttk.Label(frame_table, text="Faction", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="State", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="INF", font=FONT_HEADING_2, anchor=tk.CENTER).grid(row=0, column=col, columnspan=2, padx=2)
            ttk.Label(frame_table, text="Pri", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Sec", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Trade", font=FONT_HEADING_2, anchor=tk.CENTER).grid(row=0, column=col, columnspan=3, padx=2)
            ttk.Label(frame_table, text="Purch", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Prof", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="BM Prof", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="BVs", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Expl", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Exo", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="CBs", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Fails", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Murders", font=FONT_HEADING_2, anchor=tk.CENTER).grid(row=0, column=col, columnspan=2, padx=2, pady=2)
            ttk.Label(frame_table, text="Foot", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Ship", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Scens", font=FONT_HEADING_2).grid(row=0, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Space CZs", font=FONT_HEADING_2, anchor=tk.CENTER).grid(row=0, column=col, columnspan=3, padx=2)
            ttk.Label(frame_table, text="L", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="M", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="H", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="Foot CZs", font=FONT_HEADING_2, anchor=tk.CENTER).grid(row=0, column=col, columnspan=3, padx=2)
            ttk.Label(frame_table, text="L", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="M", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Label(frame_table, text="H", font=FONT_HEADING_2).grid(row=1, column=col, padx=2, pady=2); col += 1
            ttk.Separator(frame_table, orient=tk.HORIZONTAL).grid(columnspan=col, padx=2, pady=5, sticky=tk.EW)

            header_rows = 3
            x = 0

            for faction in system['Factions'].values():
                EnableCheckbutton = ttk.Checkbutton(frame_table)
                EnableCheckbutton.grid(row=x + header_rows, column=0, sticky=tk.N, padx=2, pady=2)
                EnableCheckbutton.configure(command=partial(self._enable_faction_change, TabParent, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system, faction, x))
                EnableCheckbutton.state(['selected', '!alternate'] if faction['Enabled'] == CheckStates.STATE_ON else ['!selected', '!alternate'])
                FactionEnableCheckbuttons.append(EnableCheckbutton)

                FactionNameFrame = ttk.Frame(frame_table)
                FactionNameFrame.grid(row=x + header_rows, column=1, sticky=tk.NW)
                FactionName = ttk.Label(FactionNameFrame, text=faction['Faction'])
                FactionName.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=2, pady=2)
                FactionName.bind("<Button-1>", partial(self._faction_name_clicked, TabParent, tab_index, EnableCheckbutton, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system, faction, x))
                settlement_row_index = 1
                for settlement_name in faction.get('GroundCZSettlements', {}):
                    SettlementCheckbutton = ttk.Checkbutton(FactionNameFrame)
                    SettlementCheckbutton.grid(row=settlement_row_index, column=0, padx=2, pady=2)
                    SettlementCheckbutton.configure(command=partial(self._enable_settlement_change, SettlementCheckbutton, settlement_name, DiscordText, activity, faction, x))
                    SettlementCheckbutton.state(['selected', '!alternate'] if faction['GroundCZSettlements'][settlement_name]['enabled'] == CheckStates.STATE_ON else ['!selected', '!alternate'])
                    SettlementName = ttk.Label(FactionNameFrame, text=f"{settlement_name} ({faction['GroundCZSettlements'][settlement_name]['type'].upper()})")
                    SettlementName.grid(row=settlement_row_index, column=1, sticky=tk.W, padx=2, pady=2)
                    SettlementName.bind("<Button-1>", partial(self._settlement_name_clicked, SettlementCheckbutton, settlement_name, DiscordText, activity, faction, x))
                    settlement_row_index += 1

                col = 2
                ttk.Label(frame_table, text=faction['FactionState']).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                MissionPointsVar = tk.IntVar(value=faction['MissionPoints']['m'])
                ttk.Spinbox(frame_table, from_=-999, to=999, width=3, textvariable=MissionPointsVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                MissionPointsVar.trace('w', partial(self._mission_points_change, TabParent, tab_index, MissionPointsVar, True, EnableAllCheckbutton, DiscordText, activity, system, faction, x))
                MissionPointsSecVar = tk.IntVar(value=faction['MissionPointsSecondary']['m'])
                ttk.Spinbox(frame_table, from_=-999, to=999, width=3, textvariable=MissionPointsSecVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                MissionPointsSecVar.trace('w', partial(self._mission_points_change, TabParent, tab_index, MissionPointsSecVar, False, EnableAllCheckbutton, DiscordText, activity, system, faction, x))
                if faction['TradePurchase'] > 0:
                    ttk.Label(frame_table, text=human_format(faction['TradePurchase'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                    ttk.Label(frame_table, text=human_format(faction['TradeProfit'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                else:
                    ttk.Label(frame_table, text=f"{human_format(faction['TradeBuy'][2]['value'])} | {human_format(faction['TradeBuy'][3]['value'])}").grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                    ttk.Label(frame_table, text=f"{human_format(faction['TradeSell'][0]['profit'])} | {human_format(faction['TradeSell'][2]['profit'])} | {human_format(faction['TradeSell'][3]['profit'])}").grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=human_format(faction['BlackMarketProfit'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=human_format(faction['Bounties'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=human_format(faction['CartData'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=human_format(faction['ExoData'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=human_format(faction['CombatBonds'])).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=faction['MissionFailed']).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=faction['GroundMurdered']).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ttk.Label(frame_table, text=faction['Murdered']).grid(row=x + header_rows, column=col, sticky=tk.N); col += 1
                ScenariosVar = tk.IntVar(value=faction['Scenarios'])
                ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=ScenariosVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                ScenariosVar.trace('w', partial(self._scenarios_change, TabParent, tab_index, ScenariosVar, EnableAllCheckbutton, DiscordText, activity, system, faction, x))

                if (faction['FactionState'] in STATES_WAR):
                    CZSpaceLVar = tk.StringVar(value=faction['SpaceCZ'].get('l', '0'))
                    ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=CZSpaceLVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                    CZSpaceMVar = tk.StringVar(value=faction['SpaceCZ'].get('m', '0'))
                    ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=CZSpaceMVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                    CZSpaceHVar = tk.StringVar(value=faction['SpaceCZ'].get('h', '0'))
                    ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=CZSpaceHVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                    CZGroundLVar = tk.StringVar(value=faction['GroundCZ'].get('l', '0'))
                    ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=CZGroundLVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                    CZGroundMVar = tk.StringVar(value=faction['GroundCZ'].get('m', '0'))
                    ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=CZGroundMVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                    CZGroundHVar = tk.StringVar(value=faction['GroundCZ'].get('h', '0'))
                    ttk.Spinbox(frame_table, from_=0, to=999, width=3, textvariable=CZGroundHVar).grid(row=x + header_rows, column=col, sticky=tk.N, padx=2, pady=2); col += 1
                    # Watch for changes on all SpinBox Variables. This approach catches any change, including manual editing, while using 'command' callbacks only catches clicks
                    CZSpaceLVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZSpaceLVar, EnableAllCheckbutton, DiscordText, CZs.SPACE_LOW, activity, system, faction, x))
                    CZSpaceMVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZSpaceMVar, EnableAllCheckbutton, DiscordText, CZs.SPACE_MED, activity, system, faction, x))
                    CZSpaceHVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZSpaceHVar, EnableAllCheckbutton, DiscordText, CZs.SPACE_HIGH, activity, system, faction, x))
                    CZGroundLVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZGroundLVar, EnableAllCheckbutton, DiscordText, CZs.GROUND_LOW, activity, system, faction, x))
                    CZGroundMVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZGroundMVar, EnableAllCheckbutton, DiscordText, CZs.GROUND_MED, activity, system, faction, x))
                    CZGroundHVar.trace('w', partial(self._cz_change, TabParent, tab_index, CZGroundHVar, EnableAllCheckbutton, DiscordText, CZs.GROUND_HIGH, activity, system, faction, x))

                x += 1

            self._update_enable_all_factions_checkbutton(TabParent, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, system)

            tab_index += 1

        self._update_discord_field(DiscordText, activity)

        # Ignore all scroll wheel events on spinboxes, to avoid accidental inputs
        self.toplevel.bind_class('TSpinbox', '<MouseWheel>', lambda event : "break")

        self._store_window_geometry()


    def _window_closed(self):
        """
        Callback for when user closes the window
        """
        self._store_window_geometry()
        self.toplevel.destroy()


    def _store_window_geometry(self):
        """
        Save the current window position and dimensions
        """
        if not self.toplevel: return

        self.window_geometry = {
            'x': self.toplevel.winfo_x(),
            'y': self.toplevel.winfo_y(),
            'w': self.toplevel.winfo_width(),
            'h': self.toplevel.winfo_height()}


    def _show_legend_window(self, event):
        """
        Display a mini-window showing a legend of all icons used
        """
        self.ui.show_legend_window()


    def _discord_button_available(self) -> bool:
        """
        Return true if the 'Post to Discord' button should be available
        """
        return self.bgstally.discord.valid_webhook_available(DiscordChannel.BGS) or self.bgstally.discord.valid_webhook_available(DiscordChannel.THARGOIDWAR)


    def _update_discord_field(self, DiscordText, activity: Activity):
        """
        Update the contents of the Discord text field
        """
        DiscordText.configure(state='normal')
        DiscordText.delete('1.0', 'end-1c')
        DiscordText.write(activity.generate_text(DiscordActivity.BOTH, True))
        DiscordText.configure(state='disabled')


    def _post_to_discord(self, activity: Activity):
        """
        Callback to post to discord in the appropriate channel(s)
        """
        if self.bgstally.state.DiscordPostStyle.get() == DiscordPostStyle.TEXT:
            discord_text:str = activity.generate_text(DiscordActivity.BGS, True)
            self.bgstally.discord.post_plaintext(discord_text, activity.discord_webhook_data, DiscordChannel.BGS, self.discord_post_complete)
            discord_text = activity.generate_text(DiscordActivity.THARGOIDWAR, True)
            self.bgstally.discord.post_plaintext(discord_text, activity.discord_webhook_data, DiscordChannel.THARGOIDWAR, self.discord_post_complete)
        else:
            description = "" if activity.discord_notes is None else activity.discord_notes
            discord_fields:dict = activity.generate_discord_embed_fields(DiscordActivity.BGS)
            self.bgstally.discord.post_embed(f"BGS Activity after tick: {activity.get_title()}", description, discord_fields, activity.discord_webhook_data, DiscordChannel.BGS, self.discord_post_complete)
            discord_fields = activity.generate_discord_embed_fields(DiscordActivity.THARGOIDWAR)
            self.bgstally.discord.post_embed(f"TW Activity after tick: {activity.get_title()}", description, discord_fields, activity.discord_webhook_data, DiscordChannel.THARGOIDWAR, self.discord_post_complete)

        activity.dirty = True # Because discord post ID has been changed


    def discord_post_complete(self, channel:DiscordChannel, webhook_data:dict, messageid:str):
        """
        A discord post request has completed
        """
        uuid:str = webhook_data.get('uuid')
        if uuid is None: return

        activity_webhook_data:dict = self.activity.discord_webhook_data.get(uuid, webhook_data) # Fetch current activity webhook data, default to data from callback.
        activity_webhook_data[channel] = messageid                                              # Store the returned messageid against the channel
        self.activity.discord_webhook_data[uuid] = activity_webhook_data                        # Store the webhook dict back to the activity


    def _discord_notes_change(self, DiscordNotesText, DiscordText, activity: Activity, *args):
        """
        Callback when the user edits the Discord notes field
        """
        activity.discord_notes = DiscordNotesText.get("1.0", "end-1c")
        self._update_discord_field(DiscordText, activity)
        DiscordNotesText.edit_modified(False) # Ensures the <<Modified>> event is triggered next edit
        activity.dirty = True


    def _option_change(self, DiscordText, activity: Activity):
        """
        Callback when one of the Discord options is changed
        """
        self.btn_post_to_discord.config(state=('normal' if self._discord_button_available() else 'disabled'))
        self._update_discord_field(DiscordText, activity)


    def _enable_faction_change(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback for when a Faction Enable Checkbutton is changed
        """
        faction['Enabled'] = CheckStates.STATE_ON if FactionEnableCheckbuttons[faction_index].instate(['selected']) else CheckStates.STATE_OFF
        self._update_enable_all_factions_checkbutton(notebook, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, system)
        self._update_discord_field(DiscordText, activity)
        activity.dirty = True


    def _enable_all_factions_change(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity: Activity, system, *args):
        """
        Callback for when the Enable All Factions Checkbutton is changed
        """
        x = 0
        for faction in system['Factions'].values():
            if EnableAllCheckbutton.instate(['selected']):
                FactionEnableCheckbuttons[x].state(['selected'])
                faction['Enabled'] = CheckStates.STATE_ON
            else:
                FactionEnableCheckbuttons[x].state(['!selected'])
                faction['Enabled'] = CheckStates.STATE_OFF
            x += 1

        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)
        self._update_discord_field(DiscordText, activity)
        activity.dirty = True


    def _enable_settlement_change(self, SettlementCheckbutton, settlement_name, DiscordText, activity: Activity, faction, faction_index, *args):
        """
        Callback for when a Settlement Enable Checkbutton is changed
        """
        faction['GroundCZSettlements'][settlement_name]['enabled'] = CheckStates.STATE_ON if SettlementCheckbutton.instate(['selected']) else CheckStates.STATE_OFF
        self._update_discord_field(DiscordText, activity)
        activity.dirty = True


    def _update_enable_all_factions_checkbutton(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, FactionEnableCheckbuttons, system):
        """
        Update the 'Enable all factions' checkbox to the correct state based on which individual factions are enabled
        """
        any_on = False
        any_off = False
        z = len(FactionEnableCheckbuttons)
        for x in range(0, z):
            if FactionEnableCheckbuttons[x].instate(['selected']): any_on = True
            if FactionEnableCheckbuttons[x].instate(['!selected']): any_off = True

        if any_on == True:
            if any_off == True:
                EnableAllCheckbutton.state(['alternate', '!selected'])
            else:
                EnableAllCheckbutton.state(['!alternate', 'selected'])
        else:
            EnableAllCheckbutton.state(['!alternate', '!selected'])

        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)


    def _faction_name_clicked(self, notebook: ScrollableNotebook, tab_index: int, EnableCheckbutton, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback when a faction name is clicked. Toggle enabled state.
        """
        if EnableCheckbutton.instate(['selected']): EnableCheckbutton.state(['!selected'])
        else: EnableCheckbutton.state(['selected'])
        self._enable_faction_change(notebook, tab_index, EnableAllCheckbutton, FactionEnableCheckbuttons, DiscordText, activity, system, faction, faction_index, *args)


    def _settlement_name_clicked(self, SettlementCheckbutton, settlement_name, DiscordText, activity: Activity, faction, faction_index, *args):
        """
        Callback when a settlement name is clicked. Toggle enabled state.
        """
        if SettlementCheckbutton.instate(['selected']): SettlementCheckbutton.state(['!selected'])
        else: SettlementCheckbutton.state(['selected'])
        self._enable_settlement_change(SettlementCheckbutton, settlement_name, DiscordText, activity, faction, faction_index, *args)


    def _cz_change(self, notebook: ScrollableNotebook, tab_index: int, CZVar, EnableAllCheckbutton, DiscordText, cz_type, activity: Activity, system, faction, faction_index, *args):
        """
        Callback (set as a variable trace) for when a CZ Variable is changed
        """
        if cz_type == CZs.SPACE_LOW:
            faction['SpaceCZ']['l'] = CZVar.get()
        elif cz_type == CZs.SPACE_MED:
            faction['SpaceCZ']['m'] = CZVar.get()
        elif cz_type == CZs.SPACE_HIGH:
            faction['SpaceCZ']['h'] = CZVar.get()
        elif cz_type == CZs.GROUND_LOW:
            faction['GroundCZ']['l'] = CZVar.get()
        elif cz_type == CZs.GROUND_MED:
            faction['GroundCZ']['m'] = CZVar.get()
        elif cz_type == CZs.GROUND_HIGH:
            faction['GroundCZ']['h'] = CZVar.get()

        activity.recalculate_zero_activity()
        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)
        self._update_discord_field(DiscordText, activity)
        activity.dirty = True


    def _mission_points_change(self, notebook: ScrollableNotebook, tab_index: int, MissionPointsVar, primary, EnableAllCheckbutton, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback (set as a variable trace) for when a mission points Variable is changed
        """
        if primary:
            faction['MissionPoints']['m'] = MissionPointsVar.get()
        else:
            faction['MissionPointsSecondary']['m'] = MissionPointsVar.get()

        activity.recalculate_zero_activity()
        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)
        self._update_discord_field(DiscordText, activity)
        activity.dirty = True


    def _scenarios_change(self, notebook: ScrollableNotebook, tab_index: int, ScenariosVar, EnableAllCheckbutton, DiscordText, activity: Activity, system, faction, faction_index, *args):
        """
        Callback (set as a variable trace) for when the scenarios Variable is changed
        """
        faction['Scenarios'] = ScenariosVar.get()

        activity.recalculate_zero_activity()
        self._update_tab_image(notebook, tab_index, EnableAllCheckbutton, system)
        self._update_discord_field(DiscordText, activity)
        activity.dirty = True


    def _update_tab_image(self, notebook: ScrollableNotebook, tab_index: int, EnableAllCheckbutton, system: dict):
        """
        Update the image alongside the tab title
        """
        if EnableAllCheckbutton.instate(['selected']):
            if system['zero_system_activity']: notebook.notebookTab.tab(tab_index, image=self.image_tab_inactive_enabled)
            else: notebook.notebookTab.tab(tab_index, image=self.image_tab_active_enabled)
        else:
            if EnableAllCheckbutton.instate(['alternate']):
                if system['zero_system_activity']: notebook.notebookTab.tab(tab_index, image=self.image_tab_inactive_part_enabled)
                else: notebook.notebookTab.tab(tab_index, image=self.image_tab_active_part_enabled)
            else:
                if system['zero_system_activity']: notebook.notebookTab.tab(tab_index, image=self.image_tab_inactive_disabled)
                else: notebook.notebookTab.tab(tab_index, image=self.image_tab_active_disabled)


    def _copy_to_clipboard(self, Form:tk.Frame, activity:Activity):
        """
        Get all text from the Discord field and put it in the Copy buffer
        """
        Form.clipboard_clear()
        Form.clipboard_append(activity.generate_text(DiscordActivity.BOTH, True))
        Form.update()

