import React from 'react';
import LineChart from './LineChart';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface SOHChartProps {
  width?: number;
  height?: number;
}

const SOHChart: React.FC<SOHChartProps> = ({ width = 300, height = 150 }) => {
  const frame = useSelector((state: RootState) => state.diagnosticFrame.frame);
  const history = useSelector((state: RootState) => state.diagnosticFrame.history);

  // Map true historical data from Redux ring buffer
  const historicalData = history.map((f, idx) => ({
    x: idx,
    y: f.stateOfHealth_value || 95.0
  }));

  if (historicalData.length === 0 && frame) {
    historicalData.push({ x: 0, y: frame.stateOfHealth_value || 95.0 });
  }

  return (
    <div className="chart-container">
      <div className="chart-title">State of Health Trend (Ring Buffer)</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Buffer Frame"
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