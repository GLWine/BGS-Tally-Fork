import json
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict

from bgstally.debug import Debug
from bgstally.constants import CheckStates
from bgstally.missionlog import MissionLog
from bgstally.state import State
from bgstally.tick import Tick

DATETIME_FORMAT_ACTIVITY = "%Y-%m-%dT%H:%M:%S.%fZ"
STATES_WAR = ['War', 'CivilWar']
STATES_ELECTION = ['Election']

# Missions that we count as +1 INF in Elections even if the Journal reports no +INF
MISSIONS_ELECTION = [
    'Mission_AltruismCredits_name',
    'Mission_Collect_name', 'Mission_Collect_Industrial_name',
    'Mission_Courier_name', 'Mission_Courier_Boom_name', 'Mission_Courier_Democracy_name', 'Mission_Courier_Elections_name', 'Mission_Courier_Expansion_name',
    'Mission_Delivery_name', 'Mission_Delivery_Agriculture_name', 'Mission_Delivery_Boom_name', 'Mission_Delivery_Confederacy_name', 'Mission_Delivery_Democracy_name',
    'Mission_Mining_name', 'Mission_Mining_Boom_name', 'Mission_Mining_Expansion_name',
    'Mission_OnFoot_Collect_MB_name',
    'Mission_OnFoot_Salvage_MB_name', 'Mission_OnFoot_Salvage_BS_MB_name',
    'Mission_PassengerBulk_name', 'Mission_PassengerBulk_AIDWORKER_ARRIVING_name', 'Mission_PassengerBulk_BUSINESS_ARRIVING_name', 'Mission_PassengerBulk_POLITICIAN_ARRIVING_name', 'Mission_PassengerBulk_SECURITY_ARRIVING_name',
    'Mission_PassengerVIP_name', 'Mission_PassengerVIP_CEO_BOOM_name', 'Mission_PassengerVIP_CEO_EXPANSION_name', 'Mission_PassengerVIP_Explorer_EXPANSION_name', 'Mission_PassengerVIP_Tourist_ELECTION_name', 'Mission_PassengerVIP_Tourist_BOOM_name',
    'Mission_Rescue_Elections_name',
    'Mission_Salvage_name', 'Mission_Salvage_Planet_name', 'MISSION_Salvage_Refinery_name',
    'MISSION_Scan_name',
    'Mission_Sightseeing_name', 'Mission_Sightseeing_Celebrity_ELECTION_name', 'Mission_Sightseeing_Tourist_BOOM_name',
    'Chain_HelpFinishTheOrder_name'
]

# Missions that we count as +1 INF in conflicts even if the Journal reports no +INF
MISSIONS_WAR = [
    'Mission_Assassinate_Legal_CivilWar_name', 'Mission_Assassinate_Legal_War_name',
    'Mission_Massacre_Conflict_CivilWar_name', 'Mission_Massacre_Conflict_War_name',
    'Mission_OnFoot_Assassination_Covert_MB_name',
    'Mission_OnFoot_Onslaught_Offline_MB_name'
]

# Missions that count towards the Thargoid War
MISSIONS_TW_COLLECT = [
    'Mission_TW_Collect_Alert_name', 'Mission_TW_CollectWing_Alert_name',
    'Mission_TW_Collect_Repairing_name', 'Mission_TW_CollectWing_Repairing_name',
    'Mission_TW_Collect_Recovery_name', 'Mission_TW_CollectWing_Recovery_name',
    'Mission_TW_Collect_UnderAttack_name', 'Mission_TW_CollectWing_UnderAttack_name'
]
MISSIONS_TW_EVAC_LOW = [
    'Mission_TW_Rescue_Alert_name', # "Evacuate n injured personnel" (cargo)
    'Mission_TW_PassengerEvacuation_Alert_name' # "n Refugees requesting evacuation" (passenger)
]
MISSIONS_TW_EVAC_MED = [
    'Mission_TW_Rescue_UnderAttack_name', # "Evacuate n wounded" (cargo)
    'Mission_TW_PassengerEvacuation_UnderAttack_name' # "n Refugees need evacuation" (passenger)
]
MISSIONS_TW_EVAC_HIGH = [
    'Mission_TW_Rescue_Burning_name', # "Evacuate n critically wounded civilians" (cargo)
    'Mission_TW_PassengerEvacuation_Burning_name' # "n Refugees need evacuation" (passenger)
]
MISSIONS_TW_MASSACRE = [
    'Mission_TW_Massacre_Scout_Singular_name', 'Mission_TW_Massacre_Scout_Plural_name',
    'Mission_TW_Massacre_Cyclops_Singular_name', 'Mission_TW_Massacre_Cyclops_Plural_name',
    'Mission_TW_Massacre_Basilisk_Singular_name', 'Mission_TW_Massacre_Basilisk_Plural_name',
    'Mission_TW_Massacre_Medusa_Singular_name', 'Mission_TW_Massacre_Medusa_Plural_name',
    'Mission_TW_Massacre_Hydra_Singular_name', 'Mission_TW_Massacre_Hydra_Plural_name',
    'Mission_TW_Massacre_Orthrus_Singular_name', 'Mission_TW_Massacre_Orthrus_Plural_name'
]

CZ_GROUND_LOW_CB_MAX = 5000
CZ_GROUND_MED_CB_MAX = 38000

TW_CBS = {65000: 's', 75000: 's', 6500000: 'c', 20000000: 'b', 25000000: 'o', 34000000: 'm', 50000000: 'h'}


class Activity:
    """
    User activity for a single tick

    Activity is stored in the self.systems Dict, with key = SystemAddress and value = Dict containing the system name and a Dict of
    factions with their activity
    """

    def __init__(self, bgstally, tick: Tick = None, discord_bgs_messageid: str = None):
        """
        Instantiate using a given Tick
        """
        self.bgstally = bgstally
        if tick == None: tick = Tick(self.bgstally)

        # Stored data. Remember to modify __deepcopy__() if these are changed or new data added.
        self.tick_id = tick.tick_id
        self.tick_time = tick.tick_time
        self.discord_bgs_messageid = discord_bgs_messageid
        self.discord_tw_messageid = None
        self.discord_notes = ""
        self.dirty: bool = False
        self.systems = {}


    def load_legacy_data(self, filepath: str):
        """
        Load and populate from a legacy (v1) data structure - i.e. the old Today Data.txt and Yesterday Data.txt files
        """
        # Convert:
        # {"1": [{"System": "Sowiio", "SystemAddress": 1458376217306, "Factions": [{}, {}], "zero_system_activity": false}]}
        # To:
        # {"tick_id": tick_id, "tick_time": tick_time, "discord_messageid": discordmessageid, "systems": {1458376217306: {"System": "Sowiio", "SystemAddress": 1458376217306, "zero_system_activity": false, "Factions": {"Faction Name 1": {}, "Faction Name 2": {}}}}}
        self.dirty = True
        with open(filepath) as legacyactivityfile:
            legacydata = json.load(legacyactivityfile)
            for legacysystemlist in legacydata.values():        # Iterate the values of the dict. We don't care about the keys - they were just "1", "2" etc.
                legacysystem = legacysystemlist[0]              # For some reason each system was a list, but always had just 1 entry
                if 'SystemAddress' in legacysystem:
                    factions = {}
                    for faction in legacysystem['Factions']:
                        factions[faction['Faction']] = faction  # Just convert List to Dict, with faction name as key

                    self.systems[str(legacysystem['SystemAddress'])] = self._get_new_system_data(legacysystem['System'], str(legacysystem['SystemAddress']), factions)
            self.recalculate_zero_activity()


    def load(self, filepath: str):
        """
        Load an activity file
        """
        with open(filepath) as activityfile:
            self._from_dict(json.load(activityfile))
            self.recalculate_zero_activity()


    def save(self, filepath: str):
        """
        Save to an activity file
        """
        if not self.dirty: return

        with open(filepath, 'w') as activityfile:
            json.dump(self._as_dict(), activityfile)
            self.dirty = False


    def get_ordered_systems(self):
        """
        Get an ordered list of the systems we are tracking, with the current system first, followed by those with activity, and finally those without
        """
        return sorted(self.systems.keys(), key=lambda x: (str(x) != self.bgstally.state.current_system_id, self.systems[x]['zero_system_activity'], self.systems[x]['System']))


    def get_current_system(self) -> dict | None:
        """
        Get the data for the current system
        """
        return self.systems.get(self.bgstally.state.current_system_id)


    def clear_activity(self, mission_log: MissionLog):
        """
        Clear down all activity. If there is a currently active mission in a system or it's the current system the player is in,
        or the system has had search and rescue items collected there, only zero the activity, otherwise delete the system completely.
        """
        self.dirty = True
        mission_systems = mission_log.get_active_systems()

        # Need to convert keys to list so we can delete as we iterate
        for system_address in list(self.systems.keys()):
            system = self.systems[system_address]
            # Note that the missions log historically stores system name so we check for that, not system address.
            # Potential for very rare bug here for systems with duplicate names.
            if system['System'] in mission_systems or \
                    self.bgstally.state.current_system_id == system_address or \
                    sum(int(d['scooped']) for d in system['TWSandR'].values()) > 0:
                # The system has a current mission, or it's the current system, or it has TWSandR scoops - zero, don't delete
                for faction_name, faction_data in system['Factions'].items():
                    system['Factions'][faction_name] = self._get_new_faction_data(faction_name, faction_data['FactionState'])
                system['TWKills'] = self._get_new_tw_kills_data()
                # Note: system['TWSandR'] data is carried forward
            else:
                # Delete the whole system
                del self.systems[system_address]


    #
    # Player Journal Log Handling
    #

    def system_entered(self, journal_entry: Dict, state: State):
        """
        The user has entered a system
        """
        try: test = journal_entry['Factions']
        except KeyError: return

        self.dirty = True
        current_system = None

        for system_address in self.systems:
            if system_address == str(journal_entry['SystemAddress']):
                # We already have an entry for this system
                current_system = self.systems[system_address]
                break

        if current_system is None:
            # We don't have this system yet
            current_system = self._get_new_system_data(journal_entry['StarSystem'], journal_entry['SystemAddress'], {})
            self.systems[str(journal_entry['SystemAddress'])] = current_system

        self._update_system_data(current_system)

        for faction in journal_entry['Factions']:
            if faction['Name'] == "Pilots' Federation Local Branch": continue

            # Ignore conflict states in FactionState as we can't trust they always come in pairs. We deal with conflicts separately below.
            faction_state = faction['FactionState'] if faction['FactionState'] not in STATES_WAR and faction['FactionState'] not in STATES_ELECTION else "None"

            if faction['Name'] in current_system['Factions']:
                # We have this faction, ensure it's up to date with latest state
                faction_data = current_system['Factions'][faction['Name']]
                self._update_faction_data(faction_data, faction_state)
            else:
                # We do not have this faction, create a new clean entry
                current_system['Factions'][faction['Name']] = self._get_new_faction_data(faction['Name'], faction_state)

        # Set war states for pairs of factions in War / Civil War / Elections
        for conflict in journal_entry.get('Conflicts', []):
            if conflict['Status'] != "active": continue

            if conflict['Faction1']['Name'] in current_system['Factions'] and conflict['Faction2']['Name'] in current_system['Factions']:
                conflict_state = "War" if conflict['WarType'] == "war" else "CivilWar" if conflict['WarType'] == "civilwar" else "Election" if conflict['WarType'] == "election" else "None"
                current_system['Factions'][conflict['Faction1']['Name']]['FactionState'] = conflict_state
                current_system['Factions'][conflict['Faction2']['Name']]['FactionState'] = conflict_state

        self.recalculate_zero_activity()
        state.current_system_id = str(current_system['SystemAddress'])
        state.system_tw_status = journal_entry.get('ThargoidWar', None)


    def mission_completed(self, journal_entry: Dict, mission_log: MissionLog):
        """
        Handle mission completed
        """
        self.dirty = True
        mission = mission_log.get_mission(journal_entry['MissionID'])

        # BGS
        for faction_effect in journal_entry['FactionEffects']:
            effect_faction_name = faction_effect['Faction']
            if faction_effect['Influence'] != []:
                inf = len(faction_effect['Influence'][0]['Influence'])
                inftrend = faction_effect['Influence'][0]['Trend']
                for system_address, system in self.systems.items():
                    if str(faction_effect['Influence'][0]['SystemAddress']) != system_address: continue

                    faction = system['Factions'].get(effect_faction_name)
                    if not faction: continue

                    # Show activity indicator
                    self.bgstally.ui.indicate_activity = True

                    if inftrend == "UpGood" or inftrend == "DownGood":
                        if effect_faction_name == journal_entry['Faction']:
                            faction['MissionPoints'] += inf
                        else:
                            faction['MissionPointsSecondary'] += inf
                    else:
                        if effect_faction_name == journal_entry['Faction']:
                            faction['MissionPoints'] -= inf
                        else:
                            faction['MissionPointsSecondary'] -= inf

            elif mission is not None:  # No influence specified for faction effect
                for system_address, system in self.systems.items():
                    if mission['System'] != system['System']: continue

                    faction = system['Factions'].get(effect_faction_name)
                    if not faction: continue

                    if (faction['FactionState'] in STATES_ELECTION and journal_entry['Name'] in MISSIONS_ELECTION) \
                    or (faction['FactionState'] in STATES_WAR and journal_entry['Name'] in MISSIONS_WAR) \
                    and effect_faction_name == journal_entry['Faction']:
                        faction['MissionPoints'] += 1
                        # Show activity indicator
                        self.bgstally.ui.indicate_activity = True

        # Thargoid War
        if journal_entry['Name'] in MISSIONS_TW_COLLECT + MISSIONS_TW_EVAC_LOW + MISSIONS_TW_EVAC_MED + MISSIONS_TW_EVAC_HIGH + MISSIONS_TW_MASSACRE and mission is not None:
            mission_station = mission.get('Station', "")
            if mission_station != "":
                for system_address, system in self.systems.items():
                    if mission['System'] != system['System']: continue
                    faction = system['Factions'].get(journal_entry['Faction'])
                    if not faction: continue

                    tw_stations = faction['TWStations']
                    if mission_station not in tw_stations:
                        tw_stations[mission_station] = self._get_new_tw_station_data(mission_station)

                    if mission.get('PassengerCount', -1) > -1:
                        # Show activity indicator
                        self.bgstally.ui.indicate_activity = True
                        if journal_entry['Name'] in MISSIONS_TW_EVAC_LOW:
                            tw_stations[mission_station]['passengers']['l']['count'] += 1
                            tw_stations[mission_station]['passengers']['l']['sum'] += mission.get('PassengerCount', -1)
                        elif journal_entry['Name'] in MISSIONS_TW_EVAC_MED:
                            tw_stations[mission_station]['passengers']['m']['count'] += 1
                            tw_stations[mission_station]['passengers']['m']['sum'] += mission.get('PassengerCount', -1)
                        elif journal_entry['Name'] in MISSIONS_TW_EVAC_HIGH:
                            tw_stations[mission_station]['passengers']['h']['count'] += 1
                            tw_stations[mission_station]['passengers']['h']['sum'] += mission.get('PassengerCount', -1)
                    elif mission.get('CommodityCount', -1) > -1:
                        # Show activity indicator
                        self.bgstally.ui.indicate_activity = True
                        match journal_entry.get('Commodity'):
                            case "$OccupiedCryoPod_Name;":
                                if journal_entry['Name'] in MISSIONS_TW_EVAC_LOW:
                                    tw_stations[mission_station]['escapepods']['l']['count'] += 1
                                    tw_stations[mission_station]['escapepods']['l']['sum'] += mission.get('CommodityCount', -1)
                                elif journal_entry['Name'] in MISSIONS_TW_EVAC_MED:
                                    tw_stations[mission_station]['escapepods']['m']['count'] += 1
                                    tw_stations[mission_station]['escapepods']['m']['sum'] += mission.get('CommodityCount', -1)
                                elif journal_entry['Name'] in MISSIONS_TW_EVAC_HIGH:
                                    tw_stations[mission_station]['escapepods']['h']['count'] += 1
                                    tw_stations[mission_station]['escapepods']['h']['sum'] += mission.get('CommodityCount', -1)
                            case _:
                                tw_stations[mission_station]['cargo']['count'] += 1
                                tw_stations[mission_station]['cargo']['sum'] += mission.get('CommodityCount', -1)
                    elif mission.get('KillCount', -1) > -1:
                        # Show activity indicator
                        self.bgstally.ui.indicate_activity = True
                        match journal_entry.get('TargetType'):
                            case "$MissionUtil_FactionTag_Scout;":
                                tw_stations[mission_station]['massacre']['s']['count'] += 1
                                tw_stations[mission_station]['massacre']['s']['sum'] += mission.get('KillCount', -1)
                            case "$MissionUtil_FactionTag_Cyclops;":
                                tw_stations[mission_station]['massacre']['c']['count'] += 1
                                tw_stations[mission_station]['massacre']['c']['sum'] += mission.get('KillCount', -1)
                            case "$MissionUtil_FactionTag_Basilisk;":
                                tw_stations[mission_station]['massacre']['b']['count'] += 1
                                tw_stations[mission_station]['massacre']['b']['sum'] += mission.get('KillCount', -1)
                            case "$MissionUtil_FactionTag_Medusa;":
                                tw_stations[mission_station]['massacre']['m']['count'] += 1
                                tw_stations[mission_station]['massacre']['m']['sum'] += mission.get('KillCount', -1)
                            case "$MissionUtil_FactionTag_Hydra;":
                                tw_stations[mission_station]['massacre']['h']['count'] += 1
                                tw_stations[mission_station]['massacre']['h']['sum'] += mission.get('KillCount', -1)
                            case "$MissionUtil_FactionTag_Orthrus;":
                                tw_stations[mission_station]['massacre']['o']['count'] += 1
                                tw_stations[mission_station]['massacre']['o']['sum'] += mission.get('KillCount', -1)

        self.recalculate_zero_activity()
        mission_log.delete_mission_by_id(journal_entry['MissionID'])


    def mission_failed(self, journal_entry: Dict, mission_log: MissionLog):
        """
        Handle mission failed
        """
        mission = mission_log.get_mission(journal_entry['MissionID'])
        if mission is None: return
        self.dirty = True

        # Show activity indicator
        self.bgstally.ui.indicate_activity = True

        for system in self.systems.values():
            if mission['System'] != system['System']: continue

            faction = system['Factions'].get(mission['Faction'])
            if faction: faction['MissionFailed'] += 1

            mission_log.delete_mission_by_id(mission['MissionID'])
            self.recalculate_zero_activity()
            break


    def exploration_data_sold(self, journal_entry: Dict, state: State):
        """
        Handle sale of exploration data
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return
        self.dirty = True

        # Show activity indicator
        self.bgstally.ui.indicate_activity = True

        faction = current_system['Factions'].get(state.station_faction)
        if faction:
            faction['CartData'] += journal_entry['TotalEarnings']
            self.recalculate_zero_activity()


    def organic_data_sold(self, journal_entry: Dict, state: State):
        """
        Handle sale of organic data
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return
        self.dirty = True

        # Show activity indicator
        self.bgstally.ui.indicate_activity = True

        faction = current_system['Factions'].get(state.station_faction)
        if faction:
            for e in journal_entry['BioData']:
                faction['ExoData'] += e['Value'] + e['Bonus']
            self.recalculate_zero_activity()


    def bv_redeemed(self, journal_entry: Dict, state: State):
        """
        Handle redemption of bounty vouchers
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return
        self.dirty = True

        # Show activity indicator
        self.bgstally.ui.indicate_activity = True

        for bv_info in journal_entry['Factions']:
            faction = current_system['Factions'].get(bv_info['Faction'])
            if faction:
                if state.station_type == 'FleetCarrier':
                    faction['Bounties'] += (bv_info['Amount'] / 2)
                else:
                    faction['Bounties'] += bv_info['Amount']
                self.recalculate_zero_activity()


    def cb_redeemed(self, journal_entry: Dict, state: State):
        """
        Handle redemption of combat bonds
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return
        self.dirty = True

        # Show activity indicator
        self.bgstally.ui.indicate_activity = True

        faction = current_system['Factions'].get(journal_entry['Faction'])
        if faction:
            faction['CombatBonds'] += journal_entry['Amount']
            self.recalculate_zero_activity()


    def trade_purchased(self, journal_entry:dict, state:State):
        """
        Handle purchase of trade commodities
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return

        faction = current_system['Factions'].get(state.station_faction)
        if faction:
            self.dirty = True
            bracket:int = 0

            # Show activity indicator
            self.bgstally.ui.indicate_activity = True

            if self.bgstally.market.available(journal_entry['MarketID']):
                market_data:dict = self.bgstally.market.get_commodity(journal_entry['Type'])
                bracket = market_data.get('StockBracket', 0)

            faction['TradeBuy'][bracket]['value'] += journal_entry['TotalCost']
            faction['TradeBuy'][bracket]['items'] += journal_entry['Count']

            self.recalculate_zero_activity()


    def trade_sold(self, journal_entry:dict, state:State):
        """
        Handle sale of trade commodities
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return

        # Handle SandR tissue samples first
        if 'thargoidtissuesample' in journal_entry.get('Type', "").lower():
            self._search_and_rescue_handin('t', journal_entry.get('Count', 0))
            # Fall through to BGS tracking for standard trade sale

        faction = current_system['Factions'].get(state.station_faction)
        if faction:
            self.dirty = True
            cost:int = journal_entry['Count'] * journal_entry['AvgPricePaid']
            profit:int = journal_entry['TotalSale'] - cost
            bracket:int = 0

            # Show activity indicator
            self.bgstally.ui.indicate_activity = True

            if journal_entry.get('BlackMarket', False):
                faction['BlackMarketProfit'] += profit
            else:
                if self.bgstally.market.available(journal_entry['MarketID']):
                    market_data:dict = self.bgstally.market.get_commodity(journal_entry['Type'])
                    bracket = market_data.get('DemandBracket', 0)

                faction['TradeSell'][bracket]['profit'] += profit
                faction['TradeSell'][bracket]['value'] += journal_entry['TotalSale']
                faction['TradeSell'][bracket]['items'] += journal_entry['Count']

            self.recalculate_zero_activity()


    def ship_targeted(self, journal_entry: Dict, state: State):
        """
        Handle targeting a ship
        """
        if 'Faction' in journal_entry and 'PilotName_Localised' in journal_entry:
            self.dirty = True
            state.last_ship_targeted = {'Faction': journal_entry['Faction'], 'PilotName_Localised': journal_entry['PilotName_Localised']}


    def crime_committed(self, journal_entry: Dict, state: State):
        """
        Handle a crime
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return
        self.dirty = True

        # For in-space murders, the faction logged in the CommitCrime event is the system faction,
        # not the ship faction. We need to log the murder against the ship faction, so we store the
        # it from the previous ShipTargeted event in last_ship_targeted.

        match journal_entry['CrimeType']:
            case 'murder':
                # For ship murders, if we didn't get a previous scan containing ship faction, don't log
                if journal_entry.get('Victim') != state.last_ship_targeted.get('PilotName_Localised'): return
                faction = current_system['Factions'].get(state.last_ship_targeted.get('Faction'))
                if faction:
                    faction['Murdered'] += 1
                    self.recalculate_zero_activity()

                    # Show activity indicator
                    self.bgstally.ui.indicate_activity = True

            case 'onFoot_murder':
                # For on-foot murders, get the faction from the journal entry
                faction = current_system['Factions'].get(journal_entry['Faction'])
                if faction:
                    faction['GroundMurdered'] += 1
                    self.recalculate_zero_activity()

                    # Show activity indicator
                    self.bgstally.ui.indicate_activity = True


    def settlement_approached(self, journal_entry: Dict, state:State):
        """
        Handle approaching a settlement
        """
        state.last_settlement_approached = {'timestamp': journal_entry['timestamp'], 'name': journal_entry['Name'], 'size': None}


    def cb_received(self, journal_entry: Dict, state: State):
        """
        Handle a combat bond received for a kill
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return

        # Check for Thargoid Kill
        if journal_entry.get('VictimFaction') == "$faction_Thargoid;":
            tw_ship:str = TW_CBS.get(journal_entry['Reward'])
            if tw_ship: current_system['TWKills'][tw_ship] += 1

            # Show activity indicator
            self.bgstally.ui.indicate_activity = True

            return

        # Otherwise, must be on-ground for CB kill tracking
        if state.last_settlement_approached == {}: return

        self.dirty = True

        # Show activity indicator
        self.bgstally.ui.indicate_activity = True

        timedifference = datetime.strptime(journal_entry['timestamp'], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(state.last_settlement_approached['timestamp'], "%Y-%m-%dT%H:%M:%SZ")
        if timedifference > timedelta(minutes=5):
            # Too long since we last approached a settlement, we can't be sure we're fighting at that settlement, clear down
            state.last_settlement_approached = {}
            return
        else:
            # We're within the timeout, refresh timestamp
            state.last_settlement_approached['timestamp'] = journal_entry['timestamp']

        # Bond issued within a short time after approaching settlement
        faction = current_system['Factions'].get(journal_entry['AwardingFaction'])
        if not faction: return

        # Add settlement to this faction's list, if not already present
        if state.last_settlement_approached['name'] not in faction['GroundCZSettlements']:
            faction['GroundCZSettlements'][state.last_settlement_approached['name']] = {'count': 0, 'enabled': CheckStates.STATE_ON, 'type': 'l'}

        # Store the previously counted size of this settlement
        previous_size = state.last_settlement_approached['size']

        # Increment this settlement's overall count if this is the first bond counted
        if state.last_settlement_approached['size'] == None:
            faction['GroundCZSettlements'][state.last_settlement_approached['name']]['count'] += 1

        # Calculate and count CZ H/M/L - Note this isn't ideal as it counts on any kill, assuming we'll win the CZ! Also note that we re-calculate on every
        # kill because when a kill is made my multiple players in a team, the CBs are split. We just hope that at some point we'll make a solo kill which will
        # put this settlement into the correct CZ size category
        if journal_entry['Reward'] < CZ_GROUND_LOW_CB_MAX:
            # Handle as 'Low' if this is the first CB
            if state.last_settlement_approached['size'] == None:
                # Increment overall 'Low' count for this faction
                faction['GroundCZ']['l'] = str(int(faction['GroundCZ'].get('l', '0')) + 1)
                # Set faction settlement type
                faction['GroundCZSettlements'][state.last_settlement_approached['name']]['type'] = 'l'
                # Store last settlement type
                state.last_settlement_approached['size'] = 'l'
        elif journal_entry['Reward'] < CZ_GROUND_MED_CB_MAX:
            # Handle as 'Med' if this is either the first CB or we've counted this settlement as a 'Low' before
            if state.last_settlement_approached['size'] == None or state.last_settlement_approached['size'] == 'l':
                # Increment overall 'Med' count for this faction
                faction['GroundCZ']['m'] = str(int(faction['GroundCZ'].get('m', '0')) + 1)
                # Decrement overall previous size count if we previously counted it
                if previous_size != None: faction['GroundCZ'][previous_size] -= 1
                # Set faction settlement type
                faction['GroundCZSettlements'][state.last_settlement_approached['name']]['type'] = 'm'
                # Store last settlement type
                state.last_settlement_approached['size'] = 'm'
        else:
            # Handle as 'High' if this is either the first CB or we've counted this settlement as a 'Low' or 'Med' before
            if state.last_settlement_approached['size'] == None or state.last_settlement_approached['size'] == 'l' or state.last_settlement_approached['size'] == 'm':
                # Increment overall 'High' count for this faction
                faction['GroundCZ']['h'] = str(int(faction['GroundCZ'].get('h', '0')) + 1)
                # Decrement overall previous size count if we previously counted it
                if previous_size != None: faction['GroundCZ'][previous_size] -= 1
                # Set faction settlement type
                faction['GroundCZSettlements'][state.last_settlement_approached['name']]['type'] = 'h'
                # Store last settlement type
                state.last_settlement_approached['size'] = 'h'

        self.recalculate_zero_activity()


    def collect_cargo(self, journal_entry: dict, state: State):
        """
        Handle cargo collection for certain cargo types
        """
        current_system = self.systems.get(state.current_system_id)
        if not current_system: return

        key:str = None

        match journal_entry.get('Type', "").lower():
            case 'damagedescapepod': key = 'dp'
            case 'occupiedcryopod': key = 'op'
            case 'usscargoblackbox': key = 'bb'
            case _ as cargo_type if "thargoidtissuesample" in cargo_type: key = 't'

        if key is None: return

        current_system['TWSandR'][key]['scooped'] += 1
        self.dirty = True


    def search_and_rescue(self, journal_entry: dict, state: State):
        """
        Handle search and rescue hand-in
        """
        key:str = None
        count:int = int(journal_entry.get('Count', 0))

        # There is no tissue sample tracking here as those are treated a commodities
        match journal_entry.get('Name', "").lower():
            case 'damagedescapepod': key = 'dp'
            case 'occupiedcryopod': key = 'op'
            case 'usscargoblackbox': key = 'bb'

        if key is None or count == 0: return

        self._search_and_rescue_handin(key, count)


    def _search_and_rescue_handin(self, key:str, count:int):
        """
        Tally a search and rescue handin. These can originate from SearchAndRescue or TradeSell events
        """

        # S&R can be handed in in any system, but the effect counts for the system the items were collected in. However,
        # we have no way of knowing exactly which items were handed in, so just iterate through all our known systems
        # looking for previously scooped cargo of the correct type.

        for system in self.systems.values():
            if count <= 0: break  # Finish when we've accounted for all items

            allocatable:int = min(count, system['TWSandR'][key]['scooped'])
            if allocatable > 0:
                system['TWSandR'][key]['scooped'] -= allocatable
                system['TWSandR'][key]['delivered'] += allocatable
                count -= allocatable
                self.dirty = True

                # Show activity indicator
                self.bgstally.ui.indicate_activity = True

        # count can end up > 0 here - i.e. more S&R handed in than we originally logged as scooped. Ignore, as we don't know
        # where it originally came from


    def player_resurrected(self):
        """
        Clear down any logged cargo on resurrect
        """
        for system in self.systems.values():
            system['TWSandR'] = self._get_new_tw_sandr_data()

        self.dirty = True


    def recalculate_zero_activity(self):
        """
        For efficiency at display time, we store whether each system has had any activity in the data structure
        """
        for system in self.systems.values():
            self._update_system_data(system)
            system['zero_system_activity'] = True

            for faction_data in system['Factions'].values():
                self._update_faction_data(faction_data)
                if not self._is_faction_data_zero(faction_data):
                    system['zero_system_activity'] = False

            if system['zero_system_activity'] == False: continue

            if sum(system['TWKills'].values()) > 0: system['zero_system_activity'] = False

            if system['zero_system_activity'] == False: continue

            if sum(int(d['delivered']) for d in system['TWSandR'].values()) > 0: system['zero_system_activity'] = False

            if system['zero_system_activity'] == False: continue


    #
    # Private functions
    #

    def _get_new_system_data(self, system_name: str, system_address: str, faction_data: Dict):
        """
        Get a new data structure for storing system data
        """
        return {'System': system_name,
                'SystemAddress': system_address,
                'zero_system_activity': True,
                'Factions': faction_data,
                'TWKills': self._get_new_tw_kills_data(),
                'TWSandR': self._get_new_tw_sandr_data()}


    def _get_new_faction_data(self, faction_name, faction_state):
        """
        Get a new data structure for storing faction data
        """
        return {'Faction': faction_name, 'FactionState': faction_state, 'Enabled': CheckStates.STATE_ON,
                'MissionPoints': 0, 'MissionPointsSecondary': 0,
                'TradeProfit': 0, 'TradePurchase': 0, 'BlackMarketProfit': 0, 'Bounties': 0, 'CartData': 0, 'ExoData': 0,
                'TradeBuy': [{'items': 0, 'value': 0}, {'items': 0, 'value': 0}, {'items': 0, 'value': 0}, {'items': 0, 'value': 0}],
                'TradeSell': [{'items': 0, 'value': 0, 'profit': 0}, {'items': 0, 'value': 0, 'profit': 0}, {'items': 0, 'value': 0, 'profit': 0}, {'items': 0, 'value': 0, 'profit': 0}],
                'CombatBonds': 0, 'MissionFailed': 0, 'Murdered': 0, 'GroundMurdered': 0,
                'SpaceCZ': {}, 'GroundCZ': {}, 'GroundCZSettlements': {}, 'Scenarios': 0,
                'TWStations': {}}


    def _get_new_tw_station_data(self, station_name):
        """
        Get a new data structure for storing Thargoid War station data
        """
        return {'name': station_name, 'enabled': CheckStates.STATE_ON,
                'passengers': {'l': {'count': 0, 'sum': 0}, 'm': {'count': 0, 'sum': 0}, 'h': {'count': 0, 'sum': 0}},
                'escapepods': {'l': {'count': 0, 'sum': 0}, 'm': {'count': 0, 'sum': 0}, 'h': {'count': 0, 'sum': 0}},
                'cargo': {'count': 0, 'sum': 0},
                'massacre': {'s': {'count': 0, 'sum': 0}, 'c': {'count': 0, 'sum': 0}, 'b': {'count': 0, 'sum': 0}, 'm': {'count': 0, 'sum': 0}, 'h': {'count': 0, 'sum': 0}, 'o': {'count': 0, 'sum': 0}}}


    def _get_new_tw_kills_data(self):
        """
        Get a new data structure for storing Thargoid War Kills
        """
        return {'s': 0, 'c': 0, 'b': 0, 'm': 0, 'h': 0, 'o': 0}


    def _get_new_tw_sandr_data(self):
        """
        Get a new data structure for storing Thargoid War Search and Rescue
        """
        return {'dp': {'scooped': 0, 'delivered': 0}, 'op': {'scooped': 0, 'delivered': 0}, 'bb': {'scooped': 0, 'delivered': 0}, 't': {'scooped': 0, 'delivered': 0}}


    def _update_system_data(self, system_data:dict):
        """
        Update system data structure for elements not present in previous versions of plugin
        """
        # From < v3.1.0 to 3.1.0
        if not 'TWKills' in system_data: system_data['TWKills'] = self._get_new_tw_kills_data()
        if not 'TWSandR' in system_data: system_data['TWSandR'] = self._get_new_tw_sandr_data()


    def _update_faction_data(self, faction_data: Dict, faction_state: str = None):
        """
        Update faction data structure for elements not present in previous versions of plugin
        """
        # Update faction state as it can change at any time post-tick
        if faction_state: faction_data['FactionState'] = faction_state

        # From < v1.2.0 to 1.2.0
        if not 'SpaceCZ' in faction_data: faction_data['SpaceCZ'] = {}
        if not 'GroundCZ' in faction_data: faction_data['GroundCZ'] = {}
        # From < v1.3.0 to 1.3.0
        if not 'Enabled' in faction_data: faction_data['Enabled'] = CheckStates.STATE_ON
        # From < v1.6.0 to 1.6.0
        if not 'MissionPointsSecondary' in faction_data: faction_data['MissionPointsSecondary'] = 0
        # From < v1.7.0 to 1.7.0
        if not 'ExoData' in faction_data: faction_data['ExoData'] = 0
        if not 'GroundCZSettlements' in faction_data: faction_data['GroundCZSettlements'] = {}
        # From < v1.8.0 to 1.8.0
        if not 'BlackMarketProfit' in faction_data: faction_data['BlackMarketProfit'] = 0
        if not 'TradePurchase' in faction_data: faction_data['TradePurchase'] = 0
        # From < v1.9.0 to 1.9.0
        if not 'Scenarios' in faction_data: faction_data['Scenarios'] = 0
        # From < v2.2.0 to 2.2.0
        if not 'TWStations' in faction_data: faction_data['TWStations'] = {}
        # 2.2.0-a1 - 2.2.0-a3 stored a single integer for passengers,  escapepods and cargo in TW station data. 2.2.0-a4 onwards has a dict for each.
        # Put the previous values for passengers and escapepods into the 'm' 'sum' entries in the dict, for want of a better place.
        # Put the previous value for cargo into the 'sum' entry in the dict.
        # The previous mission count value was aggregate across all passengers, escape pods and cargo so just plonk in escapepods for want of a better place.
        # We can remove all this code on release of final 2.2.0
        for station in faction_data['TWStations'].values():
            if not type(station.get('passengers')) == dict:
                station['passengers'] = {'l': {'count': 0, 'sum': 0}, 'm': {'count': 0, 'sum': station['passengers']}, 'h': {'count': 0, 'sum': 0}}
            if not type(station.get('escapepods')) == dict:
                station['escapepods'] = {'l': {'count': 0, 'sum': 0}, 'm': {'count': station['missions'], 'sum': station['escapepods']}, 'h': {'count': 0, 'sum': 0}}
            if not type(station.get('cargo')) == dict:
                station['cargo'] = {'count': 0, 'sum': station['cargo']}
            if not type(station.get('massacre')) == dict:
                station['massacre'] = {'s': {'count': 0, 'sum': 0}, 'c': {'count': 0, 'sum': 0}, 'b': {'count': 0, 'sum': 0}, 'm': {'count': 0, 'sum': 0}, 'h': {'count': 0, 'sum': 0}, 'o': {'count': 0, 'sum': 0}}
        # From < 3.0.0 to 3.0.0
        if not 'GroundMurdered' in faction_data: faction_data['GroundMurdered'] = 0
        if not 'TradeBuy' in faction_data:
            faction_data['TradeBuy'] = [{'items': 0, 'value': 0}, {'items': 0, 'value': 0}, {'items': 0, 'value': 0}, {'items': 0, 'value': 0}]
        if not 'TradeSell' in faction_data:
            faction_data['TradeSell'] = [{'items': 0, 'value': 0, 'profit': 0}, {'items': 0, 'value': 0, 'profit': 0}, {'items': 0, 'value': 0, 'profit': 0}, {'items': 0, 'value': 0, 'profit': 0}]


    def _is_faction_data_zero(self, faction_data: Dict):
        """
        Check whether all information is empty or zero for a faction
        """
        return int(faction_data['MissionPoints']) == 0 and int(faction_data['MissionPointsSecondary']) == 0 and \
                int(faction_data['TradeProfit']) == 0 and int(faction_data['TradePurchase']) == 0 and int(faction_data['BlackMarketProfit']) == 0 and \
                sum(int(d['value']) for d in faction_data['TradeBuy']) == 0 and \
                sum(int(d['value']) for d in faction_data['TradeSell']) == 0 and \
                int(faction_data['BlackMarketProfit']) == 0 and \
                int(faction_data['Bounties']) == 0 and int(faction_data['CartData']) == 0 and int(faction_data['ExoData']) == 0 and \
                int(faction_data['CombatBonds']) == 0 and int(faction_data['MissionFailed']) == 0 and int(faction_data['Murdered']) == 0 and int(faction_data['GroundMurdered']) == 0 and \
                (faction_data['SpaceCZ'] == {} or (int(faction_data['SpaceCZ'].get('l', 0)) == 0 and int(faction_data['SpaceCZ'].get('m', 0)) == 0 and int(faction_data['SpaceCZ'].get('h', 0)) == 0)) and \
                (faction_data['GroundCZ'] == {} or (int(faction_data['GroundCZ'].get('l', 0)) == 0 and int(faction_data['GroundCZ'].get('m', 0)) == 0 and int(faction_data['GroundCZ'].get('h', 0)) == 0)) and \
                faction_data['GroundCZSettlements'] == {} and \
                int(faction_data['Scenarios']) == 0 and \
                faction_data['TWStations'] == {}


    def _as_dict(self):
        """
        Return a Dictionary representation of our data, suitable for serializing
        """
        return {
            'tickid': self.tick_id,
            'ticktime': self.tick_time.strftime(DATETIME_FORMAT_ACTIVITY),
            'discordmessageid': self.discord_bgs_messageid,
            'discordtwmessageid': self.discord_tw_messageid,
            'discordnotes': self.discord_notes,
            'systems': self.systems}


    def _from_dict(self, dict: Dict):
        """
        Populate our data from a Dictionary that has been deserialized
        """
        self.tick_id = dict.get('tickid')
        self.tick_time = datetime.strptime(dict.get('ticktime'), DATETIME_FORMAT_ACTIVITY)
        self.discord_bgs_messageid = dict.get('discordmessageid')
        self.discord_tw_messageid = dict.get('discordtwmessageid')
        self.discord_notes = dict.get('discordnotes')
        self.systems = dict.get('systems')



    # Comparator functions - we use the tick_time for sorting

    def __eq__(self, other):
        if isinstance(other, Activity): return (self.tick_time == other.tick_time)
        return False

    def __lt__(self, other):
        if isinstance(other, Activity): return (self.tick_time < other.tick_time)
        return False

    def __le__(self, other):
        if isinstance(other, Activity): return (self.tick_time <= other.tick_time)
        return False

    def __gt__(self, other):
        if isinstance(other, Activity): return (self.tick_time > other.tick_time)
        return False

    def __ge__(self, other):
        if isinstance(other, Activity): return (self.tick_time >= other.tick_time)
        return False

    def __repr__(self):
        return f"{self.tick_id} ({self.tick_time}): {self._as_dict()}"


    # Deep copy override function - we don't deep copy any class references, just data

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        # Copied items
        setattr(result, 'bgstally', self.bgstally)
        setattr(result, 'tick_id', self.tick_id)
        setattr(result, 'tick_time', self.tick_time)
        setattr(result, 'discord_bgs_messageid', self.discord_bgs_messageid)
        setattr(result, 'discord_tw_messageid', self.discord_tw_messageid)
        setattr(result, 'discord_notes', self.discord_notes)

        # Deep copied items
        setattr(result, 'systems', deepcopy(self.systems, memo))

        return result
