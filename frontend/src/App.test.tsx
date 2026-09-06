import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { store } from './store';
import App from './App';

test('renders Unified Diagnostic Dashboard header', () => {
  render(
    <Provider store={store}>
      <App />
    </Provider>
  );
  const titleElement = screen.getByText(/Unified Diagnostic Dashboard/i);
  expect(titleElement).toBeInTheDocument();
});

test('renders ML Fusion and Active Rebalancing panels', () => {
  render(
    <Provider store={store}>
      <App />
    </Provider>
  );
  expect(screen.getByText(/ML Fusion Panel/i)).toBeInTheDocument();
  expect(screen.getByText(/Active Rebalancing Panel/i)).toBeInTheDocument();
});
