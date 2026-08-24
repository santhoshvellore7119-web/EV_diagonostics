"""
Data management module for the EV Battery Diagnostic System host application.
Handles data buffering, storage, and replay functionality.
"""

import json
import os
import numpy as np
from datetime import datetime
from .logger import get_logger


class DataManager:
    """
    Manages data buffering, recording, and playback for the host application.
    """

    def __init__(self, max_buffer_size=1000, record_dir='recordings'):
        """
        Initialize the data manager.

        Args:
            max_buffer_size (int): Maximum number of data points to keep in memory for plotting
            record_dir (str): Directory to store recording files
        """
        self.logger = get_logger(__name__)
        self.max_buffer_size = max_buffer_size
        self.record_dir = record_dir

        # Data buffers for plotting (time-series)
        self.time_buffer = np.zeros(max_buffer_size)
        self.electrical_buffer = np.zeros(max_buffer_size)
        self.ultrasonic_buffer = np.zeros(max_buffer_size)
        self.thermal_buffer = np.zeros(max_buffer_size)
        self.buffer_pointer = 0
        self.buffer_full = False

        # Recording state
        self.is_recording = False
        self.record_file = None
        self.record_start_time = None

        # Playback state
        self.is_playing = False
        self.playback_data = []
        self.playback_index = 0
        self.playback_speed = 1.0  # 1.0 = normal speed
        self.last_playback_time = None

        # Ensure record directory exists
        os.makedirs(self.record_dir, exist_ok=True)

        self.logger.info(f"DataManager initialized with buffer size {max_buffer_size}")
        self.logger.info(f"Recordings will be stored in: {os.path.abspath(self.record_dir)}")

    # ========== Buffer Management ==========

    def add_sample(self, timestamp, electrical, ultrasonic, thermal):
        """
        Add a new sample to the data buffers.

        Args:
            timestamp (float): Sample timestamp
            electrical (float): Electrical sensor value (voltage)
            ultrasonic (float): Ultrasonic sensor value (time-of-flight)
            thermal (float): Thermal sensor value (temperature)
        """
        # Store in circular buffer
        idx = self.buffer_pointer
        self.time_buffer[idx] = timestamp
        self.electrical_buffer[idx] = electrical
        self.ultrasonic_buffer[idx] = ultrasonic
        self.thermal_buffer[idx] = thermal

        # Update pointer and full flag
        self.buffer_pointer += 1
        if self.buffer_pointer >= self.max_buffer_size:
            self.buffer_pointer = 0
            self.buffer_full = True

        # Record if recording is active
        if self.is_recording:
            self._record_sample(timestamp, electrical, ultrasonic, thermal)

    def get_buffers(self):
        """
        Get the current data buffers for plotting.

        Returns:
            tuple: (time_data, electrical_data, ultrasonic_data, thermal_data)
        """
        if self.buffer_full:
            # Return buffers in chronological order
            idx = self.buffer_pointer
            time_data = np.concatenate((self.time_buffer[idx:], self.time_buffer[:idx]))
            electrical_data = np.concatenate((self.electrical_buffer[idx:], self.electrical_buffer[:idx]))
            ultrasonic_data = np.concatenate((self.ultrasonic_buffer[idx:], self.ultrasonic_buffer[:idx]))
            thermal_data = np.concatenate((self.thermal_buffer[idx:], self.thermal_buffer[:idx]))
        else:
            # Return only filled portion
            time_data = self.time_buffer[:self.buffer_pointer]
            electrical_data = self.electrical_buffer[:self.buffer_pointer]
            ultrasonic_data = self.ultrasonic_buffer[:self.buffer_pointer]
            thermal_data = self.thermal_buffer[:self.buffer_pointer]

        return time_data, electrical_data, ultrasonic_data, thermal_data

    def clear_buffers(self):
        """Clear all data buffers."""
        self.time_buffer.fill(0)
        self.electrical_buffer.fill(0)
        self.ultrasonic_buffer.fill(0)
        self.thermal_buffer.fill(0)
        self.buffer_pointer = 0
        self.buffer_full = False
        self.logger.debug("Data buffers cleared")

    # ========== Recording Functionality ==========

    def start_recording(self, filename=None):
        """
        Start recording incoming data to a file.

        Args:
            filename (str, optional): Name of the recording file. If None, generates timestamp-based name.

        Returns:
            str: Path to the recording file
        """
        if self.is_recording:
            self.logger.warning("Recording is already active")
            return None

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ev_battery_recording_{timestamp}.jsonl"

        # Ensure .jsonl extension
        if not filename.endswith('.jsonl'):
            filename += '.jsonl'

        filepath = os.path.join(self.record_dir, filename)

        try:
            self.record_file = open(filepath, 'w', encoding='utf-8')
            self.is_recording = True
            self.record_start_time = datetime.now()
            # Write header metadata
            header = {
                "type": "metadata",
                "start_time": self.record_start_time.isoformat(),
                "description": "EV Battery Diagnostic System recording",
                "version": "1.0"
            }
            self.record_file.write(json.dumps(header) + '\n')
            self.record_file.flush()
            self.logger.info(f"Started recording to {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self.is_recording = False
            return None

    def stop_recording(self):
        """
        Stop recording and close the recording file.

        Returns:
            str: Path to the recording file, or None if not recording
        """
        if not self.is_recording:
            self.logger.warning("Recording is not active")
            return None

        try:
            # Write end metadata
            end_metadata = {
                "type": "metadata",
                "end_time": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - self.record_start_time).total_seconds()
            }
            self.record_file.write(json.dumps(end_metadata) + '\n')
            self.record_file.close()
            filepath = self.record_file.name
            self.record_file = None
            self.is_recording = False
            self.record_start_time = None
            self.logger.info(f"Stopped recording. File saved: {filepath}")
            return filepath
        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")
            if self.record_file:
                self.record_file.close()
                self.record_file = None
            self.is_recording = False
            return None

    def _record_sample(self, timestamp, electrical, ultrasonic, thermal):
        """
        Internal method to record a single sample to the recording file.

        Args:
            timestamp (float): Sample timestamp
            electrical (float): Electrical sensor value
            ultrasonic (float): Ultrasonic sensor value
            thermal (float): Thermal sensor value
        """
        if not self.is_recording or not self.record_file:
            return

        try:
            sample = {
                "type": "sample",
                "timestamp": timestamp,
                "electrical": electrical,
                "ultrasonic": ultrasonic,
                "thermal": thermal
            }
            self.record_file.write(json.dumps(sample) + '\n')
            # Flush periodically to avoid data loss, but not every sample for performance
            # In a real system, you might want to flush more frequently or use buffering
        except Exception as e:
            self.logger.error(f"Failed to write sample to recording: {e}")

    # ========== Playback Functionality ==========

    def load_recording(self, filepath):
        """
        Load a recording file for playback.

        Args:
            filepath (str): Path to the recording file (.jsonl)

        Returns:
            bool: True if loaded successfully, False otherwise
        """
        if self.is_playing:
            self.logger.warning("Playback is already active. Stop current playback first.")
            return False

        if not os.path.exists(filepath):
            self.logger.error(f"Recording file not found: {filepath}")
            return False

        try:
            self.playback_data = []
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        self.playback_data.append(data)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Invalid JSON on line {line_num}: {line[:50]}... Error: {e}")

            if not self.playback_data:
                self.logger.error("No valid data found in recording file")
                return False

            # Find metadata
            metadata = [item for item in self.playback_data if item.get('type') == 'metadata']
            if metadata:
                start_time = metadata[0].get('start_time', 'Unknown')
                self.logger.info(f"Loaded recording from {start_time} with {len(self.playback_data)} total entries")
            else:
                self.logger.info(f"Loaded recording with {len(self.playback_data)} entries (no metadata found)")

            self.logger.info(f"Recording loaded successfully from {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to load recording: {e}")
            self.playback_data = []
            return False

    def start_playback(self, speed=1.0):
        """
        Start playback of the loaded recording.

        Args:
            speed (float): Playback speed multiplier (1.0 = normal speed)

        Returns:
            bool: True if playback started, False otherwise
        """
        if not self.playback_data:
            self.logger.error("No recording loaded for playback")
            return False

        if self.is_playing:
            self.logger.warning("Playback is already active")
            return False

        self.is_playing = True
        self.playback_speed = max(0.1, min(10.0, speed))  # Clamp speed between 0.1 and 10.0
        self.playback_index = 0
        self.last_playback_time = datetime.now()
        self.logger.info(f"Started playback at {self.playback_speed}x speed")
        return True

    def stop_playback(self):
        """
        Stop playback.

        Returns:
            bool: True if playback was stopped, False if not playing
        """
        if not self.is_playing:
            self.logger.warning("Playback is not active")
            return False

        self.is_playing = False
        self.logger.info("Playback stopped")
        return True

    def get_next_playback_sample(self):
        """
        Get the next sample for playback based on timing and speed.

        Returns:
            dict or None: The next playback sample, or None if playback is complete or not active
        """
        if not self.is_playing or not self.playback_data:
            return None

        # Skip metadata entries
        while self.playback_index < len(self.playback_data) and \
              self.playback_data[self.playback_index].get('type') == 'metadata':
            self.playback_index += 1

        # Check if we've reached the end
        if self.playback_index >= len(self.playback_data):
            self.logger.info("Playback completed")
            self.is_playing = False
            return None

        # Calculate time delay based on playback speed and timestamps
        current_time = datetime.now()
        if self.last_playback_time is not None:
            # For the first sample, we don't wait
            if self.playback_index > 0:
                prev_sample = self.playback_data[self.playback_index - 1]
                curr_sample = self.playback_data[self.playback_index]

                # Only process samples with timestamps
                if ('timestamp' in prev_sample and 'timestamp' in curr_sample):
                    time_diff = curr_sample['timestamp'] - prev_sample['timestamp']
                    # Apply playback speed: higher speed = shorter delay
                    delay_needed = time_diff / self.playback_speed

                    # Convert to seconds and check if enough time has passed
                    elapsed = (current_time - self.last_playback_time).total_seconds()
                    if elapsed < delay_needed:
                        # Not time yet for next sample
                        return None

        # Get the current sample
        sample = self.playback_data[self.playback_index]
        self.playback_index += 1
        self.last_playback_time = current_time

        # Return sample data in expected format
        if sample.get('type') == 'sample':
            return {
                'timestamp': sample['timestamp'],
                'electrical': sample['electrical'],
                'ultrasonic': sample['ultrasonic'],
                'thermal': sample['thermal']
            }
        else:
            # Skip non-sample entries and get next
            return self.get_next_playback_sample()

    # ========== Utility Methods ==========

    def get_recording_files(self):
        """
        Get a list of available recording files.

        Returns:
            list: List of recording file paths
        """
        if not os.path.exists(self.record_dir):
            return []

        files = []
        for f in os.listdir(self.record_dir):
            if f.endswith('.jsonl'):
                files.append(os.path.join(self.record_dir, f))
        return sorted(files, key=os.path.getmtime, reverse=True)  # Newest first

    def delete_recording(self, filepath):
        """
        Delete a recording file.

        Args:
            filepath (str): Path to the recording file to delete

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        if not os.path.exists(filepath):
            self.logger.warning(f"Recording file not found: {filepath}")
            return False

        try:
            os.remove(filepath)
            self.logger.info(f"Deleted recording: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete recording {filepath}: {e}")
            return False

    def get_recording_info(self, filepath):
        """
        Get information about a recording file.

        Args:
            filepath (str): Path to the recording file

        Returns:
            dict: Information about the recording, or None if failed
        """
        if not os.path.exists(filepath):
            return None

        try:
            stat = os.stat(filepath)
            metadata = {}
            sample_count = 0

            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if data.get('type') == 'metadata':
                            metadata.update(data)
                        elif data.get('type') == 'sample':
                            sample_count += 1
                    except json.JSONDecodeError:
                        pass

            return {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'size_bytes': stat.st_size,
                'modified_time': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'sample_count': sample_count,
                'metadata': metadata
            }
        except Exception as e:
            self.logger.error(f"Failed to get recording info for {filepath}: {e}")
            return None