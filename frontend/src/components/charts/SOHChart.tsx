import React from 'react';
import LineChart from './LineChart';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';
import { DiagnosticFrame } from '../../store/diagnosticFrameSlice';

interface SOHChartProps {
  width?: number;
  height?: number;
}

const SOHChart: React.FC<SOHChartProps> = ({ width = 300, height = 150 }) => {
  // In a real implementation, we would get historical data from the timeline slice or a separate storage
  // For now, we'll create a placeholder with some mock data
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const { frameBufferLength } = useSelector((state: RootState) => state.timeline);

  // We'll simulate having access to historical SOH data
  // In reality, this would come from a buffer of historical frames
  const historicalData = [];

  // For demonstration, if we have at least one frame, we'll create a simple trend
  if (frame && frameBufferLength > 0) {
    // Create a mock historical dataset based on current SOH with some variation
    const baseSOH = frame.stateOfHealth_value || 80;
    for (let i = 0; i < Math.min(frameBufferLength, 50); i++) {
      // Simulate SOH drifting slightly over time
      const variation = Math.sin(i * 0.1) * 2;
      const soh = Math.max(0, Math.min(100, baseSOH + variation));
      historicalData.push({ x: i, y: soh });
    }
  }

  return (
    <div className="chart-container">
      <div className="chart-title">State of Health Trend</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Time (samples)"
        yLabel="SOH (%)"
        strokeColor="#10b981"
        showPoints={false}
      />
      {frame && (
        <div className="chart-current-value">
          Current SOH: {frame.stateOfHealth_value?.toFixed(1)}%
        </div>
      )}
    </div>
  );
};

export default SOHChart;