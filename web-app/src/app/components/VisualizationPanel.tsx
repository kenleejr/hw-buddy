'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  BarElement,
  ScatterController,
  LineController,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';
import { X, Maximize2, Minimize2 } from 'lucide-react';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ScatterController,
  LineController,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface VisualizationConfig {
  visualization_type: 'linear_system' | 'quadratic' | 'linear' | 'data_chart';
  chart_config: any;
  explanation: string;
}

interface VisualizationPanelProps {
  config?: VisualizationConfig;
  isVisible: boolean;
  onClose: () => void;
}

export default function VisualizationPanel({ config, isVisible, onClose }: VisualizationPanelProps) {
  const chartRef = useRef<ChartJS>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    if (isVisible) {
      setIsAnimating(true);
      // Allow animation to complete
      const timer = setTimeout(() => setIsAnimating(false), 300);
      return () => clearTimeout(timer);
    }
  }, [isVisible]);

  if (!isVisible || !config) {
    return null;
  }

  const handleToggleExpand = () => {
    setIsExpanded(!isExpanded);
  };

  const getVisualizationTitle = () => {
    switch (config.visualization_type) {
      case 'linear_system':
        return 'System of Equations';
      case 'quadratic':
        return 'Quadratic Function';
      case 'linear':
        return 'Linear Function';
      case 'data_chart':
        return 'Data Analysis';
      default:
        return 'Visualization';
    }
  };

  const getVisualizationIcon = () => {
    switch (config.visualization_type) {
      case 'linear_system':
        return '📊';
      case 'quadratic':
        return '📈';
      case 'linear':
        return '📉';
      case 'data_chart':
        return '📋';
      default:
        return '🔍';
    }
  };

  return (
    <div 
      className={`fixed right-0 top-0 h-full bg-white shadow-2xl border-l border-gray-200 transition-all duration-300 ease-in-out z-50 ${
        isAnimating ? 'animate-pulse' : ''
      } ${
        isExpanded ? 'w-[60%] min-w-[800px]' : 'w-[40%] min-w-[500px]'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-purple-50 border-b border-gray-200">
        <div className="flex items-center space-x-3">
          <span className="text-2xl">{getVisualizationIcon()}</span>
          <div>
            <h2 className="text-lg font-semibold text-gray-800">
              {getVisualizationTitle()}
            </h2>
            <p className="text-sm text-gray-600">Interactive Visualization</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={handleToggleExpand}
            className="p-2 hover:bg-white hover:bg-opacity-60 rounded-lg transition-colors"
            title={isExpanded ? 'Minimize' : 'Maximize'}
          >
            {isExpanded ? (
              <Minimize2 className="h-5 w-5 text-gray-600" />
            ) : (
              <Maximize2 className="h-5 w-5 text-gray-600" />
            )}
          </button>
          
          <button
            onClick={onClose}
            className="p-2 hover:bg-red-50 rounded-lg transition-colors"
            title="Close visualization"
          >
            <X className="h-5 w-5 text-gray-600 hover:text-red-600" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-col h-full">
        {/* Chart Container */}
        <div className="flex-1 p-6">
          <div className="h-full w-full">
            <Chart
              ref={chartRef}
              type={config.chart_config.type || 'line'}
              data={config.chart_config.data}
              options={{
                ...config.chart_config.options,
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  ...config.chart_config.options?.plugins,
                  legend: {
                    display: true,
                    position: 'top' as const,
                    ...config.chart_config.options?.plugins?.legend,
                  },
                  title: {
                    display: true,
                    text: config.chart_config.options?.plugins?.title?.text || getVisualizationTitle(),
                    ...config.chart_config.options?.plugins?.title,
                  },
                },
                scales: {
                  ...config.chart_config.options?.scales,
                  x: {
                    display: true,
                    grid: {
                      display: true,
                      color: '#e5e7eb',
                    },
                    ...config.chart_config.options?.scales?.x,
                  },
                  y: {
                    display: true,
                    grid: {
                      display: true,
                      color: '#e5e7eb',
                    },
                    ...config.chart_config.options?.scales?.y,
                  },
                },
              }}
            />
          </div>
        </div>

        {/* Explanation */}
        <div className="p-6 bg-gray-50 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-700 mb-2">
            How this helps:
          </h3>
          <p className="text-sm text-gray-600 leading-relaxed">
            {config.explanation}
          </p>
        </div>
      </div>
    </div>
  );
}