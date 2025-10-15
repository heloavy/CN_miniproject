# Network Performance Monitor

A cross-platform web application for measuring real network performance using Windows system tools (ping, tracert, iperf3) and visualizing results in real-time with Next.js, Recharts, and React Flow.

## Features

- **Real-time Network Monitoring**: Live ping data with WebSocket streaming
- **Topology Visualization**: Interactive network topology with React Flow
- **Performance Metrics**: Latency, jitter, packet loss, bandwidth, and route hops
- **Cross-Platform Backend**: Windows-hosted Python FastAPI backend
- **Modern Frontend**: Next.js with TypeScript, Tailwind CSS, and Recharts

## Architecture

### Backend (Python FastAPI)
- **Framework**: FastAPI with async support
- **Database**: SQLite with SQLAlchemy ORM
- **Network Tools**: Windows ping, tracert, iperf3 via subprocess
- **WebSocket**: Real-time ping data streaming
- **OS Focus**: Windows for tool execution

### Frontend (Next.js)
- **Framework**: Next.js 14 with TypeScript
- **Charts**: Recharts for real-time graphs
- **Topology**: React Flow for interactive network diagrams
- **Styling**: Tailwind CSS
- **Real-time**: WebSocket client for live updates

## Prerequisites

### Windows Requirements
- Windows 10/11 (64-bit)
- Python 3.11 or higher
- Node.js 18 or higher
- Iperf3 binary

### Required Tools
- **ping** (built-in Windows tool)
- **tracert** (built-in Windows tool)
- **iperf3** (download from official website)

## Installation

### 1. Clone or Download Project
```bash
# If using git
git clone <repository-url>
cd network-performance-monitor

# Or download and extract the project files
```

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Verify iperf3 is installed and in PATH
iperf3 --version
```

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install
```

### 4. Install Iperf3 (if not already installed)
Download iperf3 for Windows from:
- https://iperf.fr/iperf-download.php
- Or install via Chocolatey: `choco install iperf3`

Ensure iperf3 is in your system PATH.

## Running the Application

### 1. Start the Backend Server
```bash
# From the backend directory
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will start on `http://localhost:8000`

### 2. Start the Frontend Development Server
```bash
# Open a new terminal, from the frontend directory
cd frontend
npm run dev
```

The frontend will start on `http://localhost:3000`

### 3. Access the Application
Open your browser and navigate to:
```
http://localhost:3000/dashboard
```

## Usage

### Network Topology
- The left pane shows an interactive network topology
- Drag and drop nodes (Laptop, PC, Server, Router)
- Connect nodes with edges
- Click on a node to select it and view details in the Inspector

### Tests
- **Ping (Live)**: Start continuous ping to selected node, view real-time latency and jitter
- **Traceroute**: Run traceroute to selected node, view hop-by-hop results
- **Iperf**: Run bandwidth test to selected node, view throughput metrics

### Real-Time Monitoring
- Live ping data updates every second via WebSocket
- Charts update in real-time using Recharts
- Connection status is displayed

## API Endpoints

### Backend API (`http://localhost:8000`)

#### Ping
- `POST /api/ping` - Execute ping test
- `WebSocket /api/ws/ping` - Real-time ping data

#### Traceroute
- `POST /api/traceroute` - Execute traceroute test
- `GET /api/traceroute/{host}` - Get traceroute history

#### Iperf
- `POST /api/iperf` - Execute iperf test
- `GET /api/iperf/{server}` - Get iperf history

#### History
- `GET /api/history?tool=...&target=...&limit=...` - Get test history

## Data Contracts

### Ping Stream Frames
```json
{
  "ts": "2023-01-01T00:00:00",
  "rtt_ms": 25.5,
  "loss_pct_window": 0.0,
  "jitter_ms_window": 2.1,
  "sample_index": 1
}
```

### Traceroute Result
```json
{
  "ts": "2023-01-01T00:00:00",
  "host": "8.8.8.8",
  "hops": [
    {"hop": 1, "ip": "192.168.1.1", "rtt_ms": 1.2},
    {"hop": 2, "ip": "10.0.0.1", "rtt_ms": 5.8}
  ]
}
```

### Iperf Result
```json
{
  "ts": "2023-01-01T00:00:00",
  "server": "8.8.8.8",
  "protocol": "TCP",
  "duration_s": 10,
  "bandwidth_mbps": 95.2,
  "jitter_ms": 0.5,
  "loss_pct": 0.0
}
```

## Project Structure

```
network-performance-monitor/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── models.py            # Pydantic schemas & SQLAlchemy models
│   │   ├── database.py          # SQLite connection
│   │   ├── services/
│   │   │   └── network_tools.py # Windows tool wrappers
│   │   └── routers/
│   │       ├── ping.py          # Ping endpoints
│   │       ├── traceroute.py    # Traceroute endpoints
│   │       ├── iperf.py         # Iperf endpoints
│   │       └── history.py       # History endpoints
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── pages/
│   │   ├── dashboard.tsx        # Main dashboard page
│   │   └── _app.tsx             # Next.js app component
│   ├── styles/
│   │   └── globals.css          # Tailwind CSS
│   ├── package.json             # Node.js dependencies
│   ├── tailwind.config.js       # Tailwind config
│   └── tsconfig.json            # TypeScript config
└── README.md                    # This file
```

## Troubleshooting

### Common Issues

1. **Backend won't start**
   - Ensure Python 3.11+ is installed
   - Install dependencies: `pip install -r requirements.txt`
   - Check if port 8000 is available

2. **Frontend won't start**
   - Ensure Node.js 18+ is installed
   - Install dependencies: `npm install`
   - Check if port 3000 is available

3. **Iperf3 tests fail**
   - Ensure iperf3 is installed and in PATH
   - Check firewall settings

4. **WebSocket connection fails**
   - Ensure backend is running
   - Check CORS settings

5. **Database errors**
   - Delete `network_monitor.db` to reset

## Security Notes

- Designed for local network monitoring
- No authentication implemented
- Database is unencrypted
- Only run on trusted networks

## Dependencies

### Backend
- **fastapi**: Modern web framework
- **uvicorn**: ASGI server
- **websockets**: WebSocket support
- **sqlalchemy**: Database ORM
- **ping3**: Ping implementation

### Frontend
- **next**: React framework
- **react**: UI library
- **recharts**: Chart library
- **@xyflow/react**: Topology visualization
- **tailwindcss**: CSS framework

## Development

### Backend Development
```bash
uvicorn app.main:app --reload
```

### Frontend Development
```bash
npm run dev
npm run build
```

## License

For educational and personal use only.

---

**Note**: This application uses Windows system tools for accurate measurements. Ensure iperf3 is properly installed for bandwidth testing.
