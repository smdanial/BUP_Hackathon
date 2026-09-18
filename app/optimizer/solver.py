import pulp
from typing import Any


def build_schedule(hours: list[dict], battery: dict, directives: list[dict]) -> dict:
    num_hours = 24

    effective_solar = []
    min_battery_reserve = []
    no_charge = [False] * num_hours
    no_discharge = [False] * num_hours
    max_grid_limit = [None] * num_hours

    for h in range(num_hours):
        solar_factor = 1.0
        reserve_req = battery.get("minimum_energy_kwh", 0.0)
        grid_cap = None
        charge_blocked = False
        discharge_blocked = False

        for d in directives:
            if not d.get("applies", False):
                continue
            adj = d.get("structured_adjustment", {})
            hours_list = adj.get("hours", [])
            if h not in hours_list:
                continue

            dtype = d.get("directive_type")
            if dtype == "solar_reduction":
                solar_factor = min(solar_factor, adj.get("factor", 1.0))
            elif dtype == "minimum_battery_reserve":
                reserve_req = max(reserve_req, adj.get("minimum_energy_kwh", 0.0))
            elif dtype == "no_charge_window":
                charge_blocked = True
            elif dtype == "no_discharge_window":
                discharge_blocked = True
            elif dtype == "max_grid_window":
                if grid_cap is None or adj.get("max_grid_kwh", float("inf")) < grid_cap:
                    grid_cap = adj.get("max_grid_kwh", float("inf"))

        effective_solar.append(hours[h].get("solar_kwh", 0.0) * solar_factor)
        min_battery_reserve.append(reserve_req)
        no_charge[h] = charge_blocked
        no_discharge[h] = discharge_blocked
        max_grid_limit[h] = grid_cap

    prob = pulp.LpProblem("GridWise_Schedule", pulp.LpMinimize)

    grid_kwh = [pulp.LpVariable(f"grid_{h}", lowBound=0) for h in range(num_hours)]
    solar_used = [pulp.LpVariable(f"solar_{h}", lowBound=0, upBound=effective_solar[h]) for h in range(num_hours)]
    bat_charge = [pulp.LpVariable(f"bat_ch_{h}", lowBound=0) for h in range(num_hours)]
    bat_discharge = [pulp.LpVariable(f"bat_dis_{h}", lowBound=0) for h in range(num_hours)]
    bat_energy = [pulp.LpVariable(f"bat_en_{h}", lowBound=min_battery_reserve[h], upBound=battery["capacity_kwh"]) for h in range(num_hours)]

    for h in range(num_hours):
        if no_charge[h]:
            prob += bat_charge[h] == 0
        else:
            prob += bat_charge[h] <= battery["max_charge_kwh_per_hour"]

        if no_discharge[h]:
            prob += bat_discharge[h] == 0
        else:
            prob += bat_discharge[h] <= battery["max_discharge_kwh_per_hour"]

        if max_grid_limit[h] is not None:
            prob += grid_kwh[h] <= max_grid_limit[h]

        demand = hours[h].get("demand_kwh", 0.0)
        prob += grid_kwh[h] + solar_used[h] + bat_discharge[h] == demand + bat_charge[h]

        if h == 0:
            prob += bat_energy[h] == battery["initial_energy_kwh"] + bat_charge[h] - bat_discharge[h]
        else:
            prob += bat_energy[h] == bat_energy[h - 1] + bat_charge[h] - bat_discharge[h]

    prob += bat_energy[num_hours - 1] == battery["initial_energy_kwh"]

    prob += pulp.lpSum(grid_kwh[h] * hours[h].get("tariff_bdt_per_kwh", 0.0) for h in range(num_hours))

    prob.solve(pulp.PULP_CBC_CMD(msg=False))

    hourly_plan = []
    total_grid = 0.0
    total_cost = 0.0
    peak_grid = 0.0

    for h in range(num_hours):
        g = pulp.value(grid_kwh[h])
        s = pulp.value(solar_used[h])
        ch = pulp.value(bat_charge[h])
        dis = pulp.value(bat_discharge[h])
        en = pulp.value(bat_energy[h])

        net_bat = ch - dis
        if net_bat > 1e-6:
            action = "charge"
            bat_kwh = ch
        elif net_bat < -1e-6:
            action = "discharge"
            bat_kwh = dis
        else:
            action = "idle"
            bat_kwh = 0.0

        tariff = hours[h].get("tariff_bdt_per_kwh", 0.0)
        hourly_plan.append({
            "hour": h,
            "grid_kwh": round(g, 4),
            "solar_used_kwh": round(s, 4),
            "battery_action": action,
            "battery_kwh": round(bat_kwh, 4),
            "battery_energy_after_kwh": round(en, 4),
        })

        total_grid += g
        total_cost += g * tariff
        peak_grid = max(peak_grid, g)

    return {
        "hourly_plan": hourly_plan,
        "total_grid_kwh": round(total_grid, 4),
        "total_cost_bdt": round(total_cost, 4),
        "peak_grid_kwh": round(peak_grid, 4),
        "plan_summary": "Optimal schedule generated.",
    }