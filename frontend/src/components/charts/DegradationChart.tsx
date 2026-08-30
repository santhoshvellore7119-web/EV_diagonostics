import React from 'react';
import LineChart from './LineChart';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface DegradationChartProps {
  width?: number;
  height?: number;
}

const DegradationChart: React.FC<DegradationChartProps> = ({ width = 300, height = 150 }) => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const { frameBufferLength } = useSelector((state: RootState) => state.timeline);

  const historicalData = [];

  if (frame && frameBufferLength > 0) {
    const baseProb = frame.degradation_probability || 0.1;
    for (let i = 0; i < Math.min(frameBufferLength, 50); i++) {
      // Simulate degradation probability changing over time
      const variation = (Math.sin(i * 0.1) * 0.1) + (Math.cos(i * 0.05) * 0.05);
      const probability = Math.max(0, Math.min(1, baseProb + variation));
      historicalData.push({ x: i, y: probability });
    }
  }

  return (
    <div className="chart-container">
      <div className="chart-title">Degradation Probability</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Time (samples)"
        yLabel="Probability"
        strokeColor="#8b5cf6"
        showPoints={false}
      />
      {frame && (
        <div className="chart-current-value">
          Current Probability: {(frame.degradation_probability * 100).toFixed(1)}%
        </div>
      )}
      <div className="chart-mode">
        Mode: {frame?.degradation_mode?.replace(/_/g, ' ').toUpperCase()}
      </div>
    </div>
  );
};

export default DegradationChart;