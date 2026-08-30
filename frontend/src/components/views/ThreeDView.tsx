import React, { useEffect, useRef } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

/**
 * 3D visualization view for both standard 3D simulation and Gazebo.
 * In a full implementation with Gazebo, this would either:
 * 1. Display Gazebo's web interface/video stream, OR
 * 2. Use Three.js to render a 3D battery model based on Gazebo-sourced data
 */
const ThreeDView: React.FC = () => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const mode = useSelector((state: RootState) => state.mode.current);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Run the effect when in 3D or Gazebo mode
    if (mode === '3d' || mode === 'gazebo') {
      // This is where we would initialize Three.js scene, camera, renderer
      // and animate the 3D battery model based on sensor data.
      console.log(`ThreeDView active in ${mode} mode - rendering 3D battery model`);

      // Cleanup on unmount or when mode changes
      return () => {
        console.log(`ThreeDView unmounting from ${mode} mode`);
      };
    }
  }, [frame, mode]);

  // Only render when in 3D or Gazebo mode
  if (mode !== '3d' && mode !== 'gazebo') {
    return null;
  }

  if (!frame) {
    return (
      <div ref={containerRef} className="view-container three-d-view">
        <div className="view-placeholder">
          <h2>{mode === 'gazebo' ? 'Gazebo Simulation' : '3D Battery Simulation'}</h2>
          <p>Waiting for simulation data...</p>
          <div className="placeholder-content">
            <div className="placeholder-icon">🔋</div>
            <p>
              {mode === 'gazebo'
                ? 'Gazebo visualization will show battery internals with real-time sensor overlays'
                : '3D visualization will show battery internals with real-time sensor overlays'}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="view-container three-d-view">
      <div className="view-header">
        <h2>{mode === 'gazebo' ? 'Gazebo Simulation' : '3D Battery Simulation'}</h2>
        <div className="view-status">
          <span className="status-indicator three-d">● {mode.toUpperCase()}</span>
          <span className="frame-id">Frame: {frame.frameId}</span>
          <span className="timestamp">
            {new Date(frame.timestamp * 1000).toLocaleTimeString()}
          </span>
        </div>
      </div>

      <div className="view-content">
        <div className="three-d-placeholder">
          <div className="placeholder-battery">
            {/* In a real implementation, this would be a Three.js render canvas */}
            <div className="placeholder-label">{mode.toUpperCase()}</div>
            <div className="placeholder-details">
              <p>State of Health: {frame.stateOfHealth_value?.toFixed(1)}%</p>
              <p>Temperature: {frame.thermal_temperature?.toFixed(1)}°C</p>
              <p>Voltage: {frame.electrical_voltage?.toFixed(2)}V</p>
              <p>Degradation: {frame.degradation_mode?.replace(/_/g, ' ')}</p>
              {mode === 'gazebo' && (
                <p>Gazebo Source: {frame.source}</p>
              )}
            </div>
          </div>
          <div className="placeholder-info">
            <h3>
              {mode === 'gazebo'
                ? 'Gazebo Simulation Information'
                : 'Simulation Information'}
            </h3>
            <p>
              This view would render a realistic 3D battery model using Three.js, showing:
            </p>
            <ul>
              <li>Internal cell structure and connections</li>
              <li>Temperature distribution (hotspots in red)</li>
              <li>Current flow vectors</li>
              <li>Mechanical stress visualization</li>
              <li>Degradation progression over time</li>
            </ul>
            <p><strong>Data Source:</strong> {frame.source?.toUpperCase()}</p>
            <p><strong>Current Mode:</strong> {mode.toUpperCase()}</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ThreeDView;