import React from 'react';
import LineChart from './LineChart';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface VoltageChartProps {
  width?: number;
  height?: number;
}

const VoltageChart: React.FC<VoltageChartProps> = ({ width = 300, height = 150 }) => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const { frameBufferLength } = useSelector((state: RootState) => state.timeline);

  const historicalData = [];

  if (frame && frameBufferLength > 0) {
    const baseVoltage = frame.electrical_voltage || 3.7;
    for (let i = 0; i < Math.min(frameBufferLength, 50); i++) {
      // Simulate voltage varying with load
      const variation = Math.sin(i * 0.15) * 0.1;
      const voltage = baseVoltage + variation;
      historicalData.push({ x: i, y: voltage });
    }
  }

  return (
    <div className="chart-container">
      <div className="chart-title">Voltage Trend</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Time (samples)"
        yLabel="Voltage (V)"
        strokeColor="#f59e0b"
        showPoints={false}
      />
      {frame && (
        <div className="chart-current-value">
          Current Voltage: {frame.electrical_voltage?.toFixed(3)} V
        </div>
      )}
    </div>
  );
};

export default VoltageChart;