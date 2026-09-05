#!/usr/bin/env python3
"""
EV Battery Diagnostics & Active Rebalancing Platform
====================================================
Master CLI orchestrator for running full-stack development servers
and invoking standalone engineering subsystems (MATLAB, Gazebo, Hardware, ML, 3D, Host).

Commands:
  python run.py fullstack     # Launch FastAPI backend + React frontend concurrently
  python run.py backend       # Launch FastAPI backend only (http://localhost:8000)
  python run.py frontend      # Launch React frontend only (http://localhost:3000)
  python run.py matlab        # Run MATLAB/Simulink Digital Twin standalone simulation
  python run.py gazebo        # Run Gazebo multi-physics & thermal simulation bridge
  python run.py hardware      # Run Hardware-in-the-Loop (HIL) test bench
  python run.py firmware      # Run Firmware validation and test suite
  python run.py 3d            # Run 3D Multi-modal physical simulation
  python run.py ml            # Run Deep Learning Multi-Modal Fusion pipeline
  python run.py host          # Run Host desktop telemetry application
  python run.py verify        # Run comprehensive verification & test suite
"""

import os
import sys
import argparse
import subprocess
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def run_fullstack(host="127.0.0.1", backend_port=8000, frontend_port=3000):
    """Launches both FastAPI backend and React frontend concurrently."""
    print("=" * 75)
    print(" [FULL-STACK] Starting EV Diagnostic Platform Dev Servers")
    print("=" * 75)
    print(f" [*] Backend URL:  http://{host}:{backend_port}")
    print(f" [*] Frontend URL: http://localhost:{frontend_port}")
    print(" [*] Press Ctrl+C to terminate both servers gracefully.\n")

    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", host,
        "--port", str(backend_port),
        "--reload"
    ]

    frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
    npm_cmd = "npm.cmd" if sys.platform.startswith("win") else "npm"
    frontend_cmd = [npm_cmd, "start"]

    processes = []
    try:
        # Start backend
        print("[*] Launching FastAPI backend...")
        p_backend = subprocess.Popen(backend_cmd, cwd=PROJECT_ROOT)
        processes.append(("Backend", p_backend))

        # Start frontend
        print("[*] Launching React frontend...")
        p_frontend = subprocess.Popen(frontend_cmd, cwd=frontend_dir)
        processes.append(("Frontend", p_frontend))

        # Monitor processes
        while True:
            for name, proc in processes:
                ret = proc.poll()
                if ret is not None:
                    print(f"\n[!] Process {name} exited with code {ret}. Shutting down remaining servers...")
                    return ret
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\n[*] Caught interrupt signal. Terminating dev servers...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"[*] Stopping {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[*] All servers stopped cleanly.")


def run_backend(host="127.0.0.1", port=8000, reload=True):
    """Runs the FastAPI backend server."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "backend.main:app",
        "--host", host,
        "--port", str(port)
    ]
    if reload:
        cmd.append("--reload")
    print(f"[*] Launching FastAPI backend on http://{host}:{port}...")
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def run_frontend():
    """Runs the React frontend development server."""
    frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
    npm_cmd = "npm.cmd" if sys.platform.startswith("win") else "npm"
    print("[*] Launching React frontend dev server on http://localhost:3000...")
    return subprocess.run([npm_cmd, "start"], cwd=frontend_dir).returncode


def run_subsystem(script_path, extra_args=None):
    """Executes a standalone subsystem runner script."""
    abs_script = os.path.join(PROJECT_ROOT, script_path)
    cmd = [sys.executable, abs_script]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def run_verification():
    """Runs the master system verification and automated pytest test suites."""
    print("=" * 75)
    print(" [VERIFY] EV Battery Diagnostics - Master Verification Suite")
    print("=" * 75)

    suites = [
        ("Architecture & Task File Structure", [sys.executable, "tests/verify_system.py"]),
        ("ML MultiBranch Fusion Network Unit Tests", [sys.executable, "-m", "pytest", "tests/test_ml_model.py", "-v"]),
        ("Active Rebalancing Decision Engine Tests", [sys.executable, "-m", "pytest", "tests/test_decision_engine.py", "-v"]),
        ("FastAPI Backend REST Endpoints", [sys.executable, "-m", "pytest", "tests/test_fastapi.py", "-v"]),
        ("Evidence & Reasoning Engine", [sys.executable, "-m", "pytest", "tests/test_evidence.py", "-v"]),
        ("Closed-Loop Rebalancing Controller", [sys.executable, "-m", "pytest", "tests/test_rebalancing.py", "-v"]),
        ("Multi-Modal Sensor Ingestion Bridge", [sys.executable, "-m", "pytest", "tests/test_ingest.py", "-v"]),
        ("Firmware Source File Structure Validation", [sys.executable, "-m", "pytest", "tests/test_main.py", "-v"]),
        ("Multi-Modal Simulation Physics Tests", [sys.executable, "-m", "pytest", "ev_cell_multimodal_sim/tests/test_simulation.py", "-v"]),
        ("Simulation Integration & SOH Tests", [sys.executable, "-m", "pytest", "ev_cell_multimodal_sim/tests/test_integration.py", "-v"]),
        ("3D Physics Simulation Unit Tests", [sys.executable, "-m", "pytest", "simulation_3d_demo/test_simulation.py", "-v"]),
        ("Hardware HIL Standalone Engine", [sys.executable, "hardware/run_hardware_hil.py", "--duration", "1.0", "--rate", "10.0"]),
        ("Gazebo Multi-Physics Bridge", [sys.executable, "gazebo/run_gazebo_sim.py", "--mode", "bridge", "--duration", "1.0", "--rate", "10.0"]),
        ("MATLAB/Simulink Digital Twin", [sys.executable, "matlab_simulink_demo/run_matlab_demo.py", "--mode", "auto", "--duration", "2.0"]),
        ("Firmware Static Verification", [sys.executable, "firmware/run_firmware_sim.py"]),
        ("ML Pipeline Smoke Test", [sys.executable, "ml_pipeline/run_ml_pipeline.py", "--mode", "fast"]),
        ("3D Physics Telemetry Engine", [sys.executable, "simulation_3d_demo/run_3d_sim.py", "--duration", "1.0"]),
        ("Host Telemetry Ingestion Bridge", [sys.executable, "host_application/run_host_app.py", "--headless", "--samples", "10"]),
    ]

    results = []
    for name, cmd in suites:
        print(f"\n>> Running: {name}")
        print("-" * 75)
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT)
        elapsed = time.time() - t0
        passed = (proc.returncode == 0)
        results.append((name, passed, elapsed))

    print("\n" + "=" * 75)
    print(" MASTER VERIFICATION SCORECARD")
    print("=" * 75)
    print(f"{'Test / Subsystem Suite':<48} | {'Status':<10} | {'Time':<8}")
    print("-" * 75)
    all_passed = True
    for name, passed, elapsed in results:
        status_str = "[ PASS ]" if passed else "[ FAIL ]"
        if not passed:
            all_passed = False
        print(f"{name:<48} | {status_str:<10} | {elapsed:>6.2f}s")
    print("=" * 75)

    if all_passed:
        print("[SUCCESS] All 18 verification suites passed with zero errors!")
        return 0
    else:
        print("[FAILURE] One or more verification suites failed.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="EV Battery Diagnostics & Rebalancing Master CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python run.py fullstack
  python run.py backend --port 8000
  python run.py matlab --mode auto --duration 5.0
  python run.py gazebo --mode bridge --duration 5.0
  python run.py hardware --duration 2.0
  python run.py 3d --duration 3.0
  python run.py ml --mode fast
  python run.py verify
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Subsystem or command to run")

    # Fullstack
    p_fs = subparsers.add_parser("fullstack", help="Run FastAPI backend + React frontend concurrently")
    p_fs.add_argument("--host", default="127.0.0.1", help="Backend host")
    p_fs.add_argument("--backend-port", type=int, default=8000, help="Backend port")
    p_fs.add_argument("--frontend-port", type=int, default=3000, help="Frontend port")

    # Backend
    p_be = subparsers.add_parser("backend", help="Run FastAPI backend")
    p_be.add_argument("--host", default="127.0.0.1", help="Host")
    p_be.add_argument("--port", type=int, default=8000, help="Port")
    p_be.add_argument("--no-reload", action="store_true", help="Disable auto-reload")

    # Frontend
    subparsers.add_parser("frontend", help="Run React frontend development server")

    # Subsystems
    subparsers.add_parser("matlab", help="Run MATLAB/Simulink Digital Twin simulation")
    subparsers.add_parser("gazebo", help="Run Gazebo multi-physics simulation bridge")
    subparsers.add_parser("hardware", help="Run Hardware-in-the-Loop (HIL) test bench")
    subparsers.add_parser("firmware", help="Run Firmware simulation & static analysis")
    subparsers.add_parser("3d", help="Run 3D Multi-modal physical simulation")
    subparsers.add_parser("ml", help="Run ML Deep Learning pipeline")
    subparsers.add_parser("host", help="Run Host telemetry application")
    subparsers.add_parser("verify", help="Run full system automated verification suite")

    args, extra = parser.parse_known_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "fullstack":
        sys.exit(run_fullstack(host=args.host, backend_port=args.backend_port, frontend_port=args.frontend_port))
    elif args.command == "backend":
        sys.exit(run_backend(host=args.host, port=args.port, reload=not args.no_reload))
    elif args.command == "frontend":
        sys.exit(run_frontend())
    elif args.command == "matlab":
        sys.exit(run_subsystem("matlab_simulink_demo/run_matlab_demo.py", extra))
    elif args.command == "gazebo":
        sys.exit(run_subsystem("gazebo/run_gazebo_sim.py", extra))
    elif args.command == "hardware":
        sys.exit(run_subsystem("hardware/run_hardware_hil.py", extra))
    elif args.command == "firmware":
        sys.exit(run_subsystem("firmware/run_firmware_sim.py", extra))
    elif args.command == "3d":
        sys.exit(run_subsystem("simulation_3d_demo/run_3d_sim.py", extra))
    elif args.command == "ml":
        sys.exit(run_subsystem("ml_pipeline/run_ml_pipeline.py", extra))
    elif args.command == "host":
        sys.exit(run_subsystem("host_application/run_host_app.py", extra))
    elif args.command == "verify":
        sys.exit(run_verification())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
