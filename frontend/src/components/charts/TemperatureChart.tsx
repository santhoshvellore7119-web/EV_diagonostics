import React from 'react';
import LineChart from './LineChart';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface TemperatureChartProps {
  width?: number;
  height?: number;
}

const TemperatureChart: React.FC<TemperatureChartProps> = ({ width = 300, height = 150 }) => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const history = useSelector((state: RootState) => state.diagnosticFrame.history);

  // Map true historical data from Redux ring buffer
  const historicalData = history.map((f, idx) => ({
    x: idx,
    y: f.thermal_temperature || 25.0
  }));

  if (historicalData.length === 0 && frame) {
    historicalData.push({ x: 0, y: frame.thermal_temperature || 25.0 });
  }

  return (
    <div className="chart-container">
      <div className="chart-title">Temperature Trend (Ring Buffer)</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Buffer Frame"
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