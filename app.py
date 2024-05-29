from flask import Flask, render_template, request, jsonify
import os
import sqlite3 as sql
import requests
from bs4 import BeautifulSoup

# app - The flask application where all the magical things are configured.
app = Flask(__name__)

# Constants - Stuff that we need to know that won't ever change!
DATABASE_FILE = "database.db"
DEFAULT_BUGGY_ID = "1"
BUGGY_RACE_SERVER_URL = "https://rhul.buggyrace.net"


def fetch_race_specs():
    response = requests.get(f"{BUGGY_RACE_SERVER_URL}/specs")

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        # Create a dictionary to store items and their costs
        items_cost_dict = {}

        # Find all tables in the HTML
        tables = soup.find_all('table', {'class': 'table'})

        index = 0

        # Iterate over each table
        for table in tables:
            index = index + 1
            # Iterate over each row in the table body
            for row in table.find('tbody').find_all('tr'):
                cols = row.find_all('td')
                if index == 2:
                    if len(cols) >= 3:  # Ensure there are enough columns
                        item = cols[2].text.strip()
                        cost = cols[3].text.strip()
                        if cost == '-' or cost == '—':  # Handle both hyphen and em dash
                            cost = 0
                        if "*" in cost:
                            cost = cost.replace("*", " ")
                            cost = int(cost)
                        else:
                            try:
                                cost = int(cost)
                            except ValueError:
                                cost = 0
                        # Add the item and cost to the dictionary
                        items_cost_dict[item] = cost



                else:
                    if len(cols) >= 3:  # Ensure there are enough columns
                        item = cols[0].text.strip()
                        cost = cols[2].text.strip()
                        if cost == '-' or cost == '—':  # Handle both hyphen and em dash
                            cost = 0
                        else:
                            try:
                                cost = int(cost)
                            except ValueError:
                                cost = 0
                        # Add the item and cost to the dictionary
                        items_cost_dict[item] = cost


        return items_cost_dict


@app.route('/')
def home():
    return render_template('index.html', server_url=BUGGY_RACE_SERVER_URL)


@app.route('/info')
def show_info():
    return render_template('info.html')


@app.route('/new', methods=['POST', 'GET'])
def create_buggy():
    if request.method == 'GET':
        con = sql.connect(DATABASE_FILE)
        con.row_factory = sql.Row
        cur = con.cursor()
        cur.execute("SELECT * FROM buggies WHERE id=?", (DEFAULT_BUGGY_ID,))
        record = cur.fetchone()
        con.close()
        return render_template("buggy-form.html", buggy=record)

    elif request.method == 'POST':
        msg = ""
        violation = ""

        # Retrieve form data
        qty_wheels = request.form['qty_wheels'].strip()
        power_type = request.form['power_type'].strip()
        power_units = request.form['power_units'].strip()
        qty_tyres = request.form['qty_tyres'].strip()
        tyres = request.form['tyres'].strip()
        flag_color = request.form['flag_color'].strip()
        flag_color_secondary = request.form['flag_color_secondary'].strip()
        flag_pattern = request.form['flag_pattern'].strip()
        total_cost = 0
        attack = request.form['attack'].strip()
        armour = request.form['armour'].strip()

        # Validate numeric fields
        if not qty_wheels.isdigit() or int(qty_wheels) % 2 != 0:
            violation = "Quantity of wheels must be an even integer."

        elif not power_units.isdigit():
            violation = "Power units must be an integer."

        elif not qty_tyres.isdigit():
            violation = "Quantity of tyres must be an integer."

        elif flag_pattern != "plain" and flag_color == flag_color_secondary:
            violation = "The secondary flag color must be different from the primary color unless the pattern is plain."

        elif int(qty_tyres) < int(qty_wheels):
            violation = "The number of tyres (includes spares) must be equal to or greater than the number of wheels."



        if violation:
            return render_template("updated.html", violation=violation)

        # Fetch race specs and calculates total costs
        race_specs = fetch_race_specs()
        total_cost += race_specs[armour]
        total_cost += race_specs[attack]
        total_cost += int(power_units) * race_specs[power_type]
        total_cost += int(qty_tyres) * race_specs[tyres]

        try:
            with sql.connect(DATABASE_FILE) as con:
                cur = con.cursor()
                cur.execute(
                    """UPDATE buggies
                       SET qty_wheels=?, power_type=?, power_units=?, qty_tyres=?, tyres=?,
                           flag_color=?, flag_color_secondary=?, flag_pattern=?,armour=?, attack=?, total_cost=?
                       WHERE id=?""",
                    (qty_wheels, power_type, power_units, qty_tyres, tyres,
                     flag_color, flag_color_secondary, flag_pattern, armour, attack, total_cost, DEFAULT_BUGGY_ID)
                )
                con.commit()
                msg = "Record successfully saved"
        except Exception as e:
            con.rollback()
            msg = f"Error in update operation: {e}"
        finally:
            con.close()

        return render_template("updated.html", msg=msg)


@app.route('/buggy')
def show_buggies():
    con = sql.connect(DATABASE_FILE)
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM buggies")
    record = cur.fetchone()
    con.close()
    return render_template("buggy.html", buggy=record)


@app.route('/edit')
def edit_buggy():
    return render_template("buggy-form.html")


@app.route('/json')
def summary():
    con = sql.connect(DATABASE_FILE)
    con.row_factory = sql.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM buggies WHERE id=? LIMIT 1", (DEFAULT_BUGGY_ID,))
    buggies = dict(zip([column[0] for column in cur.description], cur.fetchone())).items()
    con.close()
    return jsonify({key: val for key, val in buggies if (val != "" and val is not None)})


fetch_race_specs()

if __name__ == '__main__':
    alloc_port = os.environ.get('CS1999_PORT') or 5000
    debug_mode = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug_mode, host="0.0.0.0", port=int(alloc_port))
