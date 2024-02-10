import tkinter as tk
from datetime import datetime
from functools import partial
from tkinter import ttk

from bgstally.constants import CmdrInteractionReason, DATETIME_FORMAT_JOURNAL, DiscordChannel, COLOUR_HEADING_1, FONT_HEADING_1, FONT_HEADING_2
from bgstally.debug import Debug
from bgstally.widgets import TreeviewPlus
from ttkHyperlinkLabel import HyperlinkLabel
from thirdparty.colors import *

DATETIME_FORMAT_CMDRLIST = "%Y-%m-%d %H:%M:%S"


class WindowCMDRs:
    """
    Handles the CMDR list window
    """

    def __init__(self, bgstally):
        self.bgstally = bgstally

        self.selected_cmdr:dict = None
        self.target_data:list = None
        self.toplevel:tk.Toplevel = None


    def show(self):
        """
        Show our window
        """
        if self.toplevel is not None and self.toplevel.winfo_exists():
            self.toplevel.lift()
            return

        self.toplevel = tk.Toplevel(self.bgstally.ui.frame)
        self.toplevel.title("CMDR Interactions")
        self.toplevel.geometry("1200x800")

        container_frame = ttk.Frame(self.toplevel)
        container_frame.pack(fill=tk.BOTH, expand=1)

        list_frame = ttk.Frame(container_frame)
        list_frame.pack(fill=tk.BOTH, padx=5, pady=5, expand=1)

        buttons_frame = ttk.Frame(container_frame)
        buttons_frame.pack(fill=tk.X, padx=5, pady=5, side=tk.BOTTOM)

        details_frame = ttk.Frame(container_frame)
        details_frame.pack(fill=tk.X, padx=5, pady=5, side=tk.BOTTOM)

        column_info = [{'title': "Name", 'type': "name", 'align': tk.W, 'stretch': tk.YES, 'width': 200},
                        {'title': "System", 'type': "name", 'align': tk.W, 'stretch': tk.YES, 'width': 200},
                        {'title': "Squadron ID", 'type': "name", 'align': tk.CENTER, 'stretch': tk.NO, 'width': 50},
                        {'title': "Ship", 'type': "name", 'align': tk.W, 'stretch': tk.YES, 'width': 200},
                        {'title': "Legal", 'type': "name", 'align': tk.W, 'stretch': tk.NO, 'width': 60},
                        {'title': "Date / Time", 'type': "datetime", 'align': tk.CENTER, 'stretch': tk.NO, 'width': 150},
                        {'title': "Interaction", 'type': "name", 'align': tk.W, 'stretch': tk.YES, 'width': 300}]
        self.target_data = self.bgstally.target_log.get_targetlog()

        treeview = TreeviewPlus(list_frame, columns=[d['title'] for d in column_info], show="headings", callback=self._cmdr_selected, datetime_format=DATETIME_FORMAT_CMDRLIST)
        vsb = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=treeview.yview)
        vsb.pack(fill=tk.Y, side=tk.RIGHT)
        treeview.configure(yscrollcommand=vsb.set)
        treeview.pack(fill=tk.BOTH, expand=1)

        current_row = 0
        ttk.Label(details_frame, text="CMDR Details", font=FONT_HEADING_1, foreground=COLOUR_HEADING_1).grid(row=current_row, column=0, sticky=tk.W); current_row += 1
        ttk.Label(details_frame, text="Name: ", font=FONT_HEADING_2).grid(row=current_row, column=0, sticky=tk.W)
        self.cmdr_details_name = ttk.Label(details_frame, text="")
        self.cmdr_details_name.grid(row=current_row, column=1, sticky=tk.W)
        ttk.Label(details_frame, text="Inara: ", font=FONT_HEADING_2).grid(row=current_row, column=2, sticky=tk.W)
        self.cmdr_details_name_inara = HyperlinkLabel(details_frame, text="", url="https://inara.cz/elite/cmdrs/?search=aussi", underline=True)
        self.cmdr_details_name_inara.grid(row=current_row, column=3, sticky=tk.W); current_row += 1
        ttk.Label(details_frame, text="Squadron: ", font=FONT_HEADING_2).grid(row=current_row, column=0, sticky=tk.W)
        self.cmdr_details_squadron = ttk.Label(details_frame, text="")
        self.cmdr_details_squadron.grid(row=current_row, column=1, sticky=tk.W)
        ttk.Label(details_frame, text="Inara: ", font=FONT_HEADING_2).grid(row=current_row, column=2, sticky=tk.W)
        self.cmdr_details_squadron_inara = HyperlinkLabel(details_frame, text="", url="https://inara.cz/elite/squadrons-search/?search=ghst", underline=True)
        self.cmdr_details_squadron_inara.grid(row=current_row, column=3, sticky=tk.W); current_row += 1
        ttk.Label(details_frame, text="Interaction: ", font=FONT_HEADING_2).grid(row=current_row, column=0, sticky=tk.W)
        self.cmdr_details_interaction = ttk.Label(details_frame, text="")
        self.cmdr_details_interaction.grid(row=current_row, column=1, sticky=tk.W); current_row += 1

        for column in column_info:
            treeview.heading(column['title'], text=column['title'].title(), sort_by=column['type'])
            treeview.column(column['title'], anchor=column['align'], stretch=column['stretch'], width=column['width'])

        for target in reversed(self.target_data):
            target_values = [target.get('TargetName', "----"), \
                             target.get('System', "----"), \
                             target.get('SquadronID', "----"), \
                             target.get('Ship', "----"), \
                             target.get('LegalStatus', "----"), \
                             datetime.strptime(target['Timestamp'], DATETIME_FORMAT_JOURNAL).strftime(DATETIME_FORMAT_CMDRLIST), \
                             target.get('Notes', "Scanned")]
            treeview.insert("", 'end', values=target_values, iid=target.get('index'))

        self.post_button = tk.Button(buttons_frame, text="Post to Discord", command=partial(self._post_to_discord))
        self.post_button.pack(side=tk.RIGHT, padx=5, pady=5)
        self.post_button['state'] = tk.DISABLED

        self.delete_button = tk.Button(buttons_frame, text="Delete", bg="red", fg="white", command=partial(self._delete_selected, treeview))
        self.delete_button.pack(side=tk.RIGHT, padx=5, pady=5)
        self.delete_button['state'] = tk.DISABLED


    def _cmdr_selected(self, values, column, treeview:TreeviewPlus, iid:str):
        """
        A CMDR row has been clicked in the list, show details
        """
        self.cmdr_details_name.config(text = "")
        self.cmdr_details_name_inara.configure(text = "", url = "")
        self.cmdr_details_squadron.config(text = "")
        self.cmdr_details_squadron_inara.configure(text = "", url = "")
        self.cmdr_details_interaction.configure(text = "")

        # Fetch the info for this CMDR. iid is the index into the original (unsorted) CMDR list.
        self.selected_cmdr = self.target_data[int(iid)]

        if not self.selected_cmdr:
            self.post_button['state'] = tk.DISABLED
            self.delete_button['state'] = tk.DISABLED
            return
        elif self.bgstally.discord.valid_webhook_available(DiscordChannel.CMDR_INFORMATION):
            self.post_button['state'] = tk.NORMAL
            self.delete_button['state'] = tk.NORMAL

        if 'TargetName' in self.selected_cmdr: self.cmdr_details_name.config(text = self.selected_cmdr.get('TargetName'))
        if 'inaraURL' in self.selected_cmdr: self.cmdr_details_name_inara.configure(text = "Inara Info Available ⤴", url = self.selected_cmdr.get('inaraURL'))
        if 'squadron' in self.selected_cmdr:
            squadron_info = self.selected_cmdr.get('squadron')
            if 'squadronName' in squadron_info: self.cmdr_details_squadron.config(text = f"{squadron_info.get('squadronName')} ({squadron_info.get('squadronMemberRank')})")
            if 'inaraURL' in squadron_info: self.cmdr_details_squadron_inara.configure(text = "Inara Info Available ⤴", url = squadron_info.get('inaraURL'))
        elif 'SquadronID' in self.selected_cmdr:
            self.cmdr_details_squadron.config(text = f"{self.selected_cmdr.get('SquadronID')}")
        if 'Notes' in self.selected_cmdr: self.cmdr_details_interaction.config(text = self.selected_cmdr.get('Notes'))


    def _delete_selected(self, treeview:TreeviewPlus):
        """
        Delete the currently selected CMDRs
        """
        selected_items:list = treeview.selection()
        for selected_iid in selected_items:
           for i in range(len(self.target_data)):
               if self.target_data[i]['iid'] == selected_iid:
                   self.target_data.pop(i) # Remove the corresponding item
                   break
           treeview.delete(selected_iid)


    def _post_to_discord(self):
        """
        Post the current selected cmdr details to discord
        """
        if not self.selected_cmdr: return

        embed_fields = [
            {
                "name": "Name",
                "value": self.selected_cmdr.get('TargetName'),
                "inline": True
            },
            {
                "name": "In System",
                "value": self.selected_cmdr.get('System'),
                "inline": True
            },
            {
                "name": "In Ship",
                "value": self.selected_cmdr.get('Ship'),
                "inline": True
            },
            {
                "name": "In Squadron",
                "value": self.selected_cmdr.get('SquadronID'),
                "inline": True
            },
            {
                "name": "Legal Status",
                "value": self.selected_cmdr.get('LegalStatus'),
                "inline": True
            },
            {
                "name": "Date and Time",
                "value": datetime.strptime(self.selected_cmdr.get('Timestamp'), DATETIME_FORMAT_JOURNAL).strftime(DATETIME_FORMAT_CMDRLIST),
                "inline": True
            }
        ]

        if 'inaraURL' in self.selected_cmdr:
            embed_fields.append({
                "name": "CMDR Inara Link",
                "value": f"[{self.selected_cmdr.get('TargetName')}]({self.selected_cmdr.get('inaraURL')})",
                "inline": True
                })

        if 'squadron' in self.selected_cmdr:
            squadron_info = self.selected_cmdr.get('squadron')
            if 'squadronName' in squadron_info and 'inaraURL' in squadron_info:
                embed_fields.append({
                    "name": "Squadron Inara Link",
                    "value": f"[{squadron_info.get('squadronName')} ({squadron_info.get('squadronMemberRank')})]({squadron_info.get('inaraURL')})",
                    "inline": True
                    })

        description:str = ""

        match self.selected_cmdr.get('Reason'):
            case CmdrInteractionReason.FRIEND_REQUEST_RECEIVED:
                description = f"{cyan('Friend request received from this CMDR')}"
            case CmdrInteractionReason.INTERDICTED_BY:
                description = f"{red('INTERDICTED BY this CMDR')}"
            case CmdrInteractionReason.KILLED_BY:
                description = f"{red('KILLED BY this CMDR')}"
            case CmdrInteractionReason.MESSAGE_RECEIVED:
                description = f"{blue('Message received from this CMDR in local chat')}"
            case CmdrInteractionReason.TEAM_INVITE_RECEIVED:
                description = f"{green('Team invite received from this CMDR')}"
            case _:
                description = f"{yellow('I scanned this CMDR')}"

        description = f"```ansi\n{description}\n```"

        self.bgstally.discord.post_embed(f"CMDR {self.selected_cmdr.get('TargetName')}", description, embed_fields, None, DiscordChannel.CMDR_INFORMATION, None)
