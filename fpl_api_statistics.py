import requests
import os
import json

BASE_URL = 'https://fantasy.premierleague.com/api/'
TANGO_LEAGUE_ID = 5303


def update_player_collection() -> dict:
    """ Fetch all current players from FPL database including position on pitch.
    
    Parameters
    ----------
    -
    
    Returns
    -------
    player_collection: dict
        dict with player id as key. Value is dict with keys including first name, last name
        and player position.
    """
    r = requests.get(BASE_URL+'bootstrap-static/').json()

    el_type_conversion = {1: 'goalkeeper', 2: 'defender', 3: 'midfielder', 4: 'forward'}

    player_collection = {}
    for el in r['elements']:

        player_collection[el['id']] = {
            'first_name': el['first_name'],
            'second_name': el['second_name'],
            'position': el_type_conversion[el['element_type']]
        }

    """ with open('player_collection.json', 'w') as pc:
        json.dump(player_collection, pc) """

    return player_collection


def fetch_manager_information() -> dict:
    """ Fetch manager id, team name and manager name from Tangon
    
    Parameters
    ----------
    -
    
    Returns
    -------
    tango_managers: dict
        dict with manager id as key and value as dict with two keys, manager name and team name
    """
    mini_league_url = f'leagues-classic/{TANGO_LEAGUE_ID}/standings/'
    res = requests.get(os.path.join(BASE_URL, mini_league_url)).json()
    standings = res['standings']['results']

    tango_managers = {}
    for manager in standings:
        tango_managers[manager['entry']] = {
            'name': manager['player_name'],
            'team': manager['entry_name']
        }

    """ with open('tango_managers.json', 'w') as tm:
        json.dump(tango_managers, tm) """

    return tango_managers


def fetch_coach_of_the_month_and_team_value(start_gw: int, end_gw: int) -> dict:
    """ Calculate total accumulated points in a range of gameweeks for each manager
    as well as team value at start and end of range. 
    
    Parameters
    ----------
    start_gw: int
        Gameweek where calculation starts.
    end_gw: int
        Gameweek where calculation ends (inclusive upper bound). 
    
    Returns
    -------
    tango_managers: dict
        dict with manager id as key and value as dict with two keys, manager name and team name
    """
    tango_managers = fetch_manager_information()

    scores = {}

    for manager_id in tango_managers:
        manager = tango_managers[manager_id]
        manager_history_url = f'entry/{manager_id}/history'
        
        res = requests.get(os.path.join(BASE_URL, manager_history_url)).json()
        total_points = 0
        
        for gameweek in res['current']:
            if gameweek['event'] in range(start_gw, end_gw+1):
                total_points += gameweek['points']
                
                if gameweek['event'] == start_gw:
                    start_value = gameweek['value'] / 10.0
                if gameweek['event'] == end_gw:
                    end_value = gameweek['value'] / 10.0
        
        scores[manager['name']] = {'points': total_points, 'end_team_value': end_value, 'team_value_delta': end_value - start_value}

    """ with open('coach_of_the_month_and_team_value.json', 'w') as c:
        json.dump(scores, c) """

    return scores


def fetch_captain_bench_transfer(start_gw_month: int, end_gw_month:int, end_gw_total: int) \
    -> dict:
    """ Calculate total as well as monthly captain points, points on bench as well as
    number of transfers made by each tango manager. 
    
    Parameters
    ----------
    start_gw_month: int
        Gameweek where monthly calculation begins.
    end_gw:month: int
        Gameweek where monthly calculation ends (inclusive upper bound). 
    end_gw_total: int
        Gameweek where total calculation ends (inclusive upper bound).
    
    Returns
    -------
    scores: dict
        dict with team name as key and value as dict with keys for all fetched information.
    """ 

    tango_managers = fetch_manager_information()
    scores = {}

    for manager_id in tango_managers:
        manager = tango_managers[manager_id]
        scores[manager['team']] = {
            'points_on_bench_month': 0,
            'points_on_bench_total': 0,
            'number_of_transfers_month': 0,
            'number_of_transfers_total': 0,
            'captain_points_month': 0,
            'captain_points_total': 0
        } 
        for gw in range(1, end_gw_total+1):
            manager_pick_gw_url = f'entry/{manager_id}/event/{gw}/picks'
            res = requests.get(os.path.join(BASE_URL, manager_pick_gw_url)).json()

            # look up which player is captain
            picks = res['picks']
            for pick in picks:
                if pick['is_captain']:
                    captain = pick['element']

            # get data from captain
            player_url = f'element-summary/{captain}'
            res_captain = requests.get(os.path.join(BASE_URL, player_url)).json()
            captain_history = res_captain['history']

            for captain_fixture in captain_history:
                scores[manager['team']]['captain_points_total'] += captain_fixture['total_points']
                if captain_fixture['round'] in range(start_gw_month, end_gw_month+1):
                    scores[manager['team']]['captain_points_month'] += captain_fixture['total_points']

            entry = res['entry_history']

            scores[manager['team']]['points_on_bench_total'] += entry['points_on_bench']
            scores[manager['team']]['number_of_transfers_total'] += entry['event_transfers']

            if gw in range(start_gw_month, end_gw_month+1):
                scores[manager['team']]['points_on_bench_month'] += entry['points_on_bench']
                scores[manager['team']]['number_of_transfers_month'] += entry['event_transfers']

    """ with open('transfers_captain_points_and_points_on_bench.json', 'w') as t:
        json.dump(scores, t) """

    return scores


def position_bench_goals_assists_xg_xa(
    start_gw_month: int,
    end_gw_month: int,
    end_gw_total: int,
    captain_points_included: bool,
    bench_included: bool) -> dict:
    """ Calculate total as well as monthly points for each position on pitch (gk, def, mid, fwd),
    as well as number of goals, assists, xG and xA (not split per position). 
    
    Parameters
    ----------
    start_gw_month: int
        Gameweek where monthly calculation begins.
    end_gw:month: int
        Gameweek where monthly calculation ends (inclusive upper bound). 
    end_gw_total: int
        Gameweek where total calculation ends (inclusive upper bound).
    captain_points_included: bool
        If True, then points for captain are doubled for the positional calculations (i.e. the
        points that the manager got for said captain in said gameweek).
    bench_included: bool
        If True, players benched are included in the positional calculations as well as calculations
        for all other statistics extracted in this function. 
    
    Returns
    -------
    scores: dict
        dict with team name as key and value as dict with keys for all fetched information.
    """ 

    tango_managers = fetch_manager_information()
    player_collection = update_player_collection()

    scores = {}

    for manager_id in tango_managers:
        manager = tango_managers[manager_id]
        
        scores[manager['team']] = {
            'goalkeeper': {
                'total': 0,
                'month': 0
            },
            'defender': {
                'total': 0,
                'month': 0
            },
            'midfielder': {
                'total': 0,
                'month': 0
            },
            'forward': {
                'total': 0,
                'month': 0
            },
            'bench': {
                'total': 0,
                'month': 0
            },
            'goals': {
                'total': 0,
                'month': 0
            },
            'assists': {
                'total': 0,
                'month': 0
            },
            'expected_goals': {
                'total': 0.0,
                'month': 0.0
            },
            'expected_assists': {
                'total': 0.0,
                'month': 0.0
            }
        }
        
        for gw in range(1, end_gw_total+1):
            manager_pick_gw_url = f'entry/{manager_id}/event/{gw}/picks'
            res = requests.get(os.path.join(BASE_URL, manager_pick_gw_url)).json()
            
            picks = res['picks']
            for pick in picks:
                position = player_collection[pick['element']]['position']

                # scalar value (1 = normal, 2 = captain and assume 3 = triple captain)
                multiplier = pick['multiplier']

                if multiplier == 2:
                    multiplier = 1 if not captain_points_included else multiplier

                player_url = f"element-summary/{pick['element']}"

                # list of games this season with detailed data. Assume sorted hence simple indexing,
                # however if not sorted (will find out after gw2) then we can use 'round' key probably
                player_history = requests.get(os.path.join(BASE_URL, player_url)).json()['history']
                player_history_gw = player_history[gw-1]
                
                if multiplier == 0:
                    scores[manager['team']]['bench']['total'] += player_history_gw['total_points']
                    if gw in range(start_gw_month, end_gw_month+1):
                        scores[manager['team']]['bench']['month'] += player_history_gw['total_points']

                    multiplier = 1 if bench_included else multiplier

                scores[manager['team']][position]['total'] += player_history_gw['total_points'] * multiplier
                if not multiplier == 0:
                    scores[manager['team']]['goals']['total'] += player_history_gw['goals_scored']
                    scores[manager['team']]['assists']['total'] += player_history_gw['assists']
                    scores[manager['team']]['expected_goals']['total'] += float(player_history_gw['expected_goals'])
                    scores[manager['team']]['expected_assists']['total'] += float(player_history_gw['expected_assists'])
                if gw in range(start_gw_month, end_gw_month+1):
                    scores[manager['team']][position]['month'] += player_history_gw['total_points'] * multiplier

                    if not multiplier == 0:
                        scores[manager['team']]['goals']['month'] += player_history_gw['goals_scored']
                        scores[manager['team']]['assists']['month'] += player_history_gw['assists']
                        scores[manager['team']]['expected_goals']['month'] += float(player_history_gw['expected_goals'])
                        scores[manager['team']]['expected_assists']['month'] += float(player_history_gw['expected_assists'])
        
        scores[manager['team']]['expected_goals']['total'] = round(scores[manager['team']]['expected_goals']['total'], 2) 
        scores[manager['team']]['expected_goals']['month'] = round(scores[manager['team']]['expected_goals']['month'], 2) 
        scores[manager['team']]['expected_assists']['total'] = round(scores[manager['team']]['expected_assists']['total'], 2) 
        scores[manager['team']]['expected_assists']['month'] = round(scores[manager['team']]['expected_assists']['month'], 2)

    return scores

    """ with open('bus_midfield_attack_bench_goals_assists_xg_xa.json', 'w') as b:
        json.dump(scores, b) """


def least_and_most_points(start_gw_month: int, end_gw_month: int) -> dict:
    """  Calculate least and most accumulated points in a single gameweek for each manager,
    both on a total as well as monthly basis.

    Parameters
    ----------
    start_gw_month: int
        Gameweek where monthly calculation begins.
    end_gw:month: int
        Gameweek where monthly calculation ends (inclusive upper bound). 
    
    Returns
    -------
    scores: dict
        dict with team name as key and value as dict with keys for all fetched information.
    
    """
    tango_managers = fetch_manager_information()

    scores = {}

    for manager_id in tango_managers:
        manager = tango_managers[manager_id]
        
        manager_history_url = f'entry/{manager_id}/history'
        manager_history = requests.get(os.path.join(BASE_URL, manager_history_url)).json()

        manager_scores = {
            'min_points_total': None,
            'max_points_total': None,
            'min_points_month': None,
            'max_points_month': None
        }
        
        for gw in manager_history['current']:
            if gw['event'] == 1:
                manager_scores['min_points_total'] = gw['total_points']
                manager_scores['max_points_total'] = gw['total_points']
            if gw['event'] == start_gw_month:
                manager_scores['min_points_month'] = gw['total_points']   
                manager_scores['max_points_month'] = gw['total_points']   
            if gw['event'] > 1:
                if gw['total_points'] < manager_scores['min_points_total']:
                    manager_scores['min_points_total'] = gw['total_points']
                if gw['total_points'] > manager_scores['max_points_total']:
                    manager_scores['max_points_total'] = gw['total_points']
                
                if gw['event'] in range(start_gw_month, end_gw_month+1):
                    if gw['total_points'] < manager_scores['min_points_month']:
                        manager_scores['min_points_month'] = gw['total_points']
                    if gw['total_points'] > manager_scores['max_points_month']:
                        manager_scores['max_points_month'] = gw['total_points']
        
        scores[manager['team']] = manager_scores

    return scores

    """ with open('least_and_most_points_total_and_month.json', 'w') as l:
        json.dump(scores, l) """


if __name__ == '__main__':
    
    update_player_collection()
    fetch_manager_information()
    
    gw_start_of_month = 1
    gw_end_of_month = 1
    gw_end_total = 1
    
    functions = {
        'coach_of_the_month_and_team_value': [
            fetch_coach_of_the_month_and_team_value,
            [gw_start_of_month, gw_end_of_month]
        ],
        'captain_points_bench_points_num_of_transfers': [
            fetch_captain_bench_transfer,
            [gw_start_of_month, gw_end_of_month, gw_end_total]
        ],
        'position_points_bench_points_goals_assists_xg_xa': [
            position_bench_goals_assists_xg_xa,
            [gw_start_of_month, gw_end_of_month, gw_end_total, True, False]
        ],
        'least_and_most_points': [
            least_and_most_points,
            [gw_start_of_month, gw_end_of_month]
        ]
    }
    
    for func_key in functions:
        function_setup = functions[func_key]
        func = function_setup[0]
        args = function_setup[1]
        
        stats = func(*args)
        
        with open(f"{func_key}.json", 'w') as f:
            json.dump(stats, f)