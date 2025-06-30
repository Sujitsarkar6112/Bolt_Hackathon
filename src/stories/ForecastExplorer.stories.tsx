import type { Meta, StoryObj } from '@storybook/react';
import { ForecastExplorer } from '../pages/ForecastExplorer';

const meta: Meta<typeof ForecastExplorer> = {
  title: 'Pages/ForecastExplorer',
  component: ForecastExplorer,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'Advanced forecast exploration page with dual-axis charts, model comparison, and KPI metrics.'
      }
    }
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof ForecastExplorer>;

export const Default: Story = {
  name: 'Default View',
  parameters: {
    docs: {
      description: {
        story: 'Default forecast explorer with ensemble model selected and 30-day horizon.'
      }
    }
  }
};

export const ProphetModel: Story = {
  name: 'Prophet Model',
  parameters: {
    docs: {
      description: {
        story: 'Forecast explorer using Facebook Prophet model for seasonal pattern analysis.'
      }
    }
  }
};

export const TFTModel: Story = {
  name: 'TFT Model',
  parameters: {
    docs: {
      description: {
        story: 'Forecast explorer using Temporal Fusion Transformer for advanced ML predictions.'
      }
    }
  }
};

export const LongTermForecast: Story = {
  name: 'Long-term Forecast',
  parameters: {
    docs: {
      description: {
        story: 'Extended 180-day forecast view showing long-term trend predictions.'
      }
    }
  }
};

export const LoadingState: Story = {
  name: 'Loading State',
  parameters: {
    docs: {
      description: {
        story: 'Loading state while forecast data is being generated.'
      }
    }
  }
};

export const ErrorState: Story = {
  name: 'Error State',
  parameters: {
    docs: {
      description: {
        story: 'Error state when forecast generation fails.'
      }
    }
  }
};