import React from 'react';

interface LineChartProps {
  data: { x: number; y: number }[];
  width?: number;
  height?: number;
  xLabel?: string;
  yLabel?: string;
  strokeColor?: string;
  showPoints?: boolean;
}

const LineChart: React.FC<LineChartProps> = ({
  data,
  width = 300,
  height = 150,
  xLabel = '',
  yLabel = '',
  strokeColor = '#3b82f6',
  showPoints = true
}) => {
  if (data.length === 0) {
    return (
      <div style={{ width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}>
        No data available
      </div>
    );
  }

  // Calculate scales
  const xMin = Math.min(...data.map(d => d.x));
  const xMax = Math.max(...data.map(d => d.x));
  const yMin = Math.min(...data.map(d => d.y));
  const yMax = Math.max(...data.map(d => d.y));

  // Add padding
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  const xPadding = xRange * 0.05;
  const yPadding = yRange * 0.05;
  const xScale = (width - 60) / (xRange + 2 * xPadding);
  const yScale = (height - 40) / (yRange + 2 * yPadding);

  // Convert data to screen coordinates
  const points = data.map(d => ({
    x: 40 + (d.x - (xMin - xPadding)) * xScale,
    y: height - 20 - (d.y - (yMin - yPadding)) * yScale
  }));

  // Create SVG path for the line
  const path = points
    .map((p, i) => (i === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
    .join(' ');

  return (
    <div style={{ width, height, fontFamily: 'system-ui, sans-serif' }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
        {/* Axes */}
        <line x1={40} y1={height - 20} x2={width - 20} y2={height - 20} stroke="#9ca3af" strokeWidth={1} />
        <line x1={40} y1={20} x2={40} y2={height - 20} stroke="#9ca3af" strokeWidth={1} />

        {/* Labels */}
        <text x={width / 2} y={height - 5} textAnchor="middle" fontSize={12} fill="#6b7280">
          {xLabel}
        </text>
        <text x={15} y={height / 2} textAnchor="middle" fontSize={12} fill="#6b7280" transform={`rotate(-90,15,${height / 2})`}>
          {yLabel}
        </text>

        {/* Grid lines (light) */}
        {[0, 0.25, 0.5, 0.75, 1].map(ratio => {
          const y = height - 20 - ratio * (height - 40);
          return (
            <line
              key={`h-${ratio}`}
              x1={40}
              y1={y}
              x2={width - 20}
              y2={y}
              stroke="#e5e7eb"
              strokeWidth={0.5}
            />
          );
        })}

        {/* Data points */}
        {showPoints &&
          points.map((p, i) => (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r={3}
              fill={strokeColor}
            />
          ))}

        {/* Line */}
        <path
          d={path}
          fill="none"
          stroke={strokeColor}
          strokeWidth={2}
        />
      </svg>
    </div>
  );
};

export default LineChart;