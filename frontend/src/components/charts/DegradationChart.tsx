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
  const history = useSelector((state: RootState) => state.diagnosticFrame.history);

  const currentMode = frame?.degradation_mode || 'healthy';
  const isHealthy = currentMode === 'healthy';
  const confidence = frame?.degradation_probability !== undefined ? frame.degradation_probability : 0.95;
  const degradationRisk = isHealthy ? Math.max(0, 1.0 - confidence) : confidence;

  // Map historical data from Redux ring buffer
  const historicalData = history.map((f, idx) => {
    const fMode = f.degradation_mode || 'healthy';
    const fConf = f.degradation_probability !== undefined ? f.degradation_probability : 0.95;
    const fRisk = fMode === 'healthy' ? Math.max(0, 1.0 - fConf) : fConf;
    return {
      x: idx,
      y: fRisk
    };
  });

  if (historicalData.length === 0) {
    historicalData.push({ x: 0, y: degradationRisk });
  }

  return (
    <div className="chart-container">
      <div className="chart-title">AI Fault Risk & Mode Confidence</div>
      <LineChart
        data={historicalData}
        width={width}
        height={height}
        xLabel="Buffer Frame"
        yLabel="Fault Risk"
        strokeColor={isHealthy ? '#10b981' : '#f59e0b'}
        showPoints={false}
      />
      {frame && (
        <div className="chart-current-value" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>
            <strong>Fault Risk:</strong> {(degradationRisk * 100).toFixed(1)}%
          </span>
          <span style={{ color: isHealthy ? '#34d399' : '#fbbf24', fontSize: '0.78rem', fontWeight: 600 }}>
            ({(confidence * 100).toFixed(1)}% {currentMode.replace(/_/g, ' ').toUpperCase()})
          </span>
        </div>
      )}
      <div className="chart-mode" style={{ marginTop: '2px', fontSize: '0.75rem', color: isHealthy ? '#10b981' : '#f59e0b' }}>
        ● Diagnostic Status: {isHealthy ? 'NORMAL / HEALTHY' : `DEGRADATION (${currentMode.replace(/_/g, ' ').toUpperCase()})`}
      </div>
    </div>
  );
};

export default DegradationChart;