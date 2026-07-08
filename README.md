# IEEE TIP Student Branch Officer Availability

A desktop application built with **PyQt6** that allows officers of the **IEEE Technological Institute of the Philippines Student Branch** to quickly check officer availability based on the organization's non-availability timetable.

Instead of manually scanning an entire spreadsheet, the application automatically computes officer availability and provides multiple ways to query schedules.

---

## Features

* 📂 Import timetable CSV files dynamically
* 👤 Automatically detect officer names from the imported timetable
* 📅 Full Availability Mode

  * Displays every free time window for a selected officer
* ⏰ Range Mode

  * Checks whether an officer is available within a specified day and time range
* 📋 Schedule Mode

  * Displays every recorded non-availability entry for an officer
* ⚙️ Settings page for loading and reloading timetable files
* 🖥️ Standalone desktop application built with PyQt6
* 🔄 Compatible with future timetable CSVs that follow the same format

---

## How It Works

The application is based on the IEEE TIP Student Branch's **Officer Non-Availability Timetable**.

Each timetable cell contains the names of officers who are **busy** during that 30-minute time slot.

If an officer's name **does not appear** in a particular time slot, the application considers that officer **available** for that period.

Consecutive available slots are merged into larger availability windows for easier viewing.

### Example

| Time  | Tuesday |
| ----- | ------- |
| 9:00  | John    |
| 9:30  |         |
| 10:00 |         |
| 10:30 | John    |

Result:

```
John is available from 9:30 to 10:30
```

---

## Application Modes

### Full Availability

Returns every available time window for a selected officer across one day or the entire week.

---

### Range Mode

Checks whether an officer is available between a selected start time and end time on a chosen day.

If the officer is unavailable, the application displays the conflicting time slots.

---

### Schedule Mode

Displays every timetable entry where the selected officer is marked as unavailable.

---

### Settings

Allows users to:

* Import a timetable CSV
* Reload the current timetable
* View timetable statistics
* View detected officers and available days

---

## CSV Format

The application expects a CSV structured similarly to the following:

| Time | Monday | Tuesday |
|------|---------|----------|
| 7:30 | Officer A<br>Officer B<br>Officer C | Officer D |
| 8:00 | Officer A | Officer B |


Each cell contains newline-separated officer names.
The application automatically detects all officer names.

---

## Installation

Clone the repository:

```bash
git clone https://github.com/<username>/ieee-officer-availability.git
cd ieee-officer-availability
```

Install the required packages:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
python ieee_availability_app.py
```

---

## Building an Executable

Install PyInstaller:

```bash
pip install pyinstaller
```

Generate a standalone executable:

```bash
pyinstaller -F -w --name "IEEE Officer Availability" ieee_availability_app.py
```

The executable will be generated in:

```
dist/
```

---

## Technologies Used

* Python 3
* PyQt6
* CSV (Python Standard Library)

---

## Acknowledgements

This project was developed for the **IEEE Technological Institute of the Philippines Student Branch** to simplify officer schedule management and improve coordination among officers.

The software architecture, testing, and integration were designed by the project developer. The implementation were generated with the assistance of Claude Sonnet 5 and were subsequently reviewed, integrated, and adapted to meet the project's functional requirements.

This project was made with the authorization of the then-chair of the IEEE TIP Student Branch.

---

## License

This project is intended for educational and organizational use within the IEEE TIP Student Branch.

Please consult the repository's `LICENSE` file for licensing information.
