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
  const history = useSelector((state: RootState) => state.diagnosticFrame.history);

  // Map true historical data from Redux ring buffer
  const historicalData = history.map((f, idx) => ({
    x: idx,
    y: f.electrical_voltage || 3.60
  }));

  // Fallback single point if history is empty
  if (historicalData.length === 0 && frame) {
    historicalData.push({ x: 0, y: frame.electrical_voltage || 3.60 });
  }

  return (
    <div className="chart-container">
      <div className="chart-title">Voltage Trend (Ring Buffer)</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Buffer Frame"
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