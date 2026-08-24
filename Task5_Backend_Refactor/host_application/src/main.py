"""
Main entry point for the EV Battery Diagnostic System host application.
Initializes and runs the application with all components properly connected.
"""

import sys
from PyQt5 import QtWidgets
from .host_app import HostApp
from .logger import setup_logger, get_logger


def main():
    """Main application entry point."""
    # Setup logging first
    logger = setup_logger(
        name='ev_battery_diagnostic',
        log_level=20,  # INFO level
        log_dir='logs'
    )

    logger.info("=" * 50)
    logger.info("EV Battery Diagnostic System - Starting Application")
    logger.info("=" * 50)

    try:
        # Create Qt application
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationName("EV Battery Diagnostic System")
        app.setApplicationVersion("1.0")

        # Create and show main window
        win = HostApp()
        win.show()

        logger.info("Application started successfully")
        logger.info("Entering Qt event loop")

        # Start the event loop
        sys.exit(app.exec_())

    except Exception as e:
        logger.critical(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()