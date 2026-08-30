import React from 'react';
import LineChart from './LineChart';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';
import { DiagnosticFrame } from '../../store/diagnosticFrameSlice';

interface TemperatureChartProps {
  width?: number;
  height?: number;
}

const TemperatureChart: React.FC<TemperatureChartProps> = ({ width = 300, height = 150 }) => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const { frameBufferLength } = useSelector((state: RootState) => state.timeline);

  const historicalData = [];

  if (frame && frameBufferLength > 0) {
    const baseTemp = frame.thermal_temperature || 25;
    for (let i = 0; i < Math.min(frameBufferLength, 50); i++) {
      // Simulate temperature varying with operation
      const variation = Math.sin(i * 0.2) * 3;
      const temperature = baseTemp + variation;
      historicalData.push({ x: i, y: temperature });
    }
  }

  return (
    <div className="chart-container">
      <div className="chart-title">Temperature Trend</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Time (samples)"
        yLabel="Temperature (°C)"
        strokeColor="#ef4444"
        showPoints={false}
      />
      {frame && (
        <div className="chart-current-value">
          Current Temperature: {frame.thermal_temperature?.toFixed(2)}°C
        </div>
      )}
    </div>
  );
};

export default TemperatureChart;