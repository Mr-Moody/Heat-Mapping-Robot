#  ThermalScout

## Installation

### Backend
Install virtual environment and packages with uv by running:
```bash
uv sync
```

### Frontend
Entering the folder frontend with:
 ```bash
 cd frontend
 ```

 Install packages with:
 ```bash
 npm install
 ```

## Usage

### Backend
Enter backend with:
```bash
cd backend
```

Enter virtual environment with:
```bash
.venv\Scripts\activate
```

Run backend with:
```bash
uv run python main.py
```


### Frontend
Enter frontend folder with:
```bash
cd frontend/RobotDashboard
```

Run frontend with:
```bash
npm run dev
```

## Important information
The frontend and backend are built to be dynamic with connection to the robot. When your device is connected to the robot and it is powered, the backend will initiate either a serial or WiFi connection. This allows the streaming of sensor data to the python backend, as well as python to control the robot with path finding algorithms.

This system is still fully functional without the robot connection, however the Physical Robot in the side panel will not load, but the additional simulation robots will work as expected.


---

Submission for HackLondon 2026 Hardware track. Built by Thomas Moody, Naerthi Senthilkumar, Helitha Cooray.