"""
Live Diagnostic View - Primary page showing real-time multi-modal diagnostics.
"""

import streamlit as st
import numpy as np
import torch
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sys
import os
from datetime import datetime
import time

# Add the project root to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from core.physics_engine import simulate_cell_response, to_csv
from core.virtual_daq import VirtualDAQ
from models.fusion_net import MultiBranchFusionNet
from control.decision_engine import DecisionEngine, SystemState
from control.rebalancing_sim import RebalancingSimulator
from config import params as P

# Page configuration
st.set_page_config(
    page_title="Live Diagnostic View",
    page_icon="🔋",
    layout="wide"
)

def create_signal_plots(electrical, ultrasonic, thermal, time_s, confidences=None):
    """Create interactive plots for the three modality signals."""
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=('Electrical Signal (Voltage)', 'Ultrasonic Signal', 'Thermal Signal (Temperature Rise)'),
        vertical_spacing=0.08
    )

    # Electrical signal
    fig.add_trace(
        go.Scatter(x=time_s, y=electrical['voltage'], name='Voltage (V)', line=dict(color='#FF6B6B')),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=time_s, y=electrical['current'], name='Current (A)', line=dict(color='#4ECDC4'), yaxis='y2'),
        row=1, col=1, secondary_y=True
    )

    # Ultrasonic signal
    fig.add_trace(
        go.Scatter(x=time_s, y=ultrasonic['signal'], name='Ultrasonic Signal', line=dict(color='#45B7D1')),
        row=2, col=1
    )

    # Thermal signal
    fig.add_trace(
        go.Scatter(x=time_s, y=thermal['temperature_rise'], name='Temperature Rise (K)', line=dict(color='#96CEB4')),
        row=3, col=1
    )

    # Update layout
    fig.update_layout(
        height=600,
        showlegend=True,
        title_text="Multi-Modal Sensor Signals (Time-Aligned to Excitation Pulse)",
        hovermode='x unified'
    )

    # Update y-axis labels
    fig.update_yaxes(title_text="Voltage (V)", row=1, col=1)
    fig.update_yaxes(title_text="Current (A)", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Signal Amplitude", row=2, col=1)
    fig.update_yaxes(title_text="Temperature Rise (K)", row=3, col=1)

    # Update x-axis labels (only show on bottom plot)
    fig.update_xaxes(title_text="Time (s)", row=3, col=1)

    return fig

def create_confidence_bars(confidences):
    """Create a horizontal bar chart showing modality confidences."""
    if confidences is None:
        # Default values if no confidences provided
        confidences = {
            'electrical': 0.62,
            'ultrasonic': 0.25,
            'thermal': 0.13
        }

    modalities = ['Electrical', 'Ultrasonic', 'Thermal']
    values = [confidences.get('electrical', 0) * 100,
              confidences.get('ultrasonic', 0) * 100,
              confidences.get('thermal', 0) * 100]
    colors = ['#FF6B6B', '#45B7D1', '#96CEB4']

    fig = go.Figure(data=[
        go.Bar(
            y=modalities,
            x=values,
            orientation='h',
            marker_color=colors,
            text=[f'{v:.1f}%' for v in values],
            textposition='auto',
        )
    ])

    fig.update_layout(
        title="Modality Confidence Weights (Confidence-Weighted Attention)",
        xaxis_title="Confidence (%)",
        height=200,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    return fig

def create_soh_gauge(soh_mean, soh_var=None):
    """Create a gauge showing SOH with optional confidence interval."""
    if soh_var is not None:
        soh_std = np.sqrt(soh_var)
        lower_bound = max(0, soh_mean - 2*soh_std)
        upper_bound = min(100, soh_mean + 2*soh_std)
    else:
        lower_bound = soh_mean
        upper_bound = soh_mean

    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = soh_mean,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "State of Health (SOH) with Confidence Interval"},
        delta = {'reference': 100},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "darkblue"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 50], 'color': 'lightgray'},
                {'range': [50, 80], 'color': 'gray'}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90}}))

    # Add confidence interval as a transparent bar
    fig.add_trace(go.Bar(
        x=[upper_bound - lower_bound],
        y=[0.5],
        base=lower_bound,
        orientation='h',
        marker=dict(color='rgba(255,165,0,0.3)', line=dict(width=0)),
        showlegend=False,
        hoverinfo='none'
    ))

    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))

    return fig

def create_state_machine_indicator(current_state):
    """Create a horizontal state machine diagram with current state highlighted."""
    states = [
        ("IDLE", "⚪"),
        ("SENSING", "🔵"),
        ("ANALYZING", "🟡"),
        ("RESENSING", "🟠"),
        ("REBALANCING", "🟢"),
        ("VERIFYING", "🟣"),
        ("COMPLETE", "⚫")
    ]

    # Create columns for each state
    cols = st.columns(len(states))

    for i, (state_name, emoji) in enumerate(states):
        with cols[i]:
            if state_name == current_state:
                # Highlight current state
                st.markdown(f"<div style='text-align: center;'><div style='font-size: 2rem;'>{emoji}</div><p style='font-weight: bold; color: #FF6B6B;'>{state_name}</p></div>", unsafe_allow_html=True)
            else:
                # Normal state
                st.markdown(f"<div style='text-align: center;'><div style='font-size: 2rem;'>{emoji}</div><p>{state_name}</p></div>", unsafe_allow_html=True)

def main():
    st.title("🔋 Live Diagnostic View")
    st.markdown("### Real-Time Multi-Modal Battery Diagnostics")

    # Sidebar controls
    st.sidebar.header("Simulation Controls")

    # Degradation mode selection
    degradation_mode = st.sidebar.selectbox(
        "Degradation Mode",
        options=['healthy', 'li_plating', 'active_material_loss', 'electrolyte_decomposition', 'gas_generation', 'internal_short'],
        index=0
    )

    # SOC slider
    soc = st.sidebar.slider("State of Charge (SOC)", 0.0, 1.0, 0.5, 0.01)

    # Noise level
    noise_level = st.sidebar.slider("Noise Level", 0.0, 1.0, 0.1, 0.01)

    # Run simulation button
    if st.sidebar.button("🔄 Run Diagnostic Cycle", type="primary"):
        # Simulate cell response
        with st.spinner("Simulating cell response..."):
            # Update params with noise level
            params = P.copy()
            params['ELECTRICAL_NOISE_STD_V'] = 0.001 * (1 + noise_level)
            params['ULTRASONIC_TOF_NOISE_STD_S'] = 1e-9 * (1 + noise_level)
            params['THERMAL_NOISE_STD_K'] = 0.01 * (1 + noise_level)

            # Simulate cell response
            results = simulate_cell_response(soc, degradation_mode, add_noise=True)

            # Process through virtual DAQ
            daq = VirtualDAQ()
            processed = daq.process_cycle(results)

            # Simulate ML inference (placeholder - in real implementation would use trained model)
            # For now, generate reasonable outputs based on degradation mode
            mode_to_idx = {
                'healthy': 0,
                'li_plating': 1,
                'active_material_loss': 2,
                'electrolyte_decomposition': 3,
                'gas_generation': 4,
                'internal_short': 5
            }
            mode_idx = mode_to_idx[degradation_mode]

            # Simulate model outputs with some uncertainty
            # In reality, these would come from the trained MultiBranchFusionNet
            degradation_prob = 0.7 + 0.2 * np.random.random()  # Base probability plus randomness
            # Adjust probability based on how distinct the degradation signature is
            if degradation_mode == 'healthy':
                degradation_prob = 0.6 + 0.3 * np.random.random()
            elif degradation_mode in ['gas_generation', 'internal_short']:
                degradation_prob = 0.8 + 0.15 * np.random.random()  # Easier to detect
            else:
                degradation_prob = 0.7 + 0.25 * np.random.random()

            # Clamp probability
            degradation_prob = min(0.95, max(0.5, degradation_prob))

            # SOH estimation with uncertainty
            base_soh = {
                'healthy': 95.0,
                'li_plating': 88.0,
                'active_material_loss': 82.0,
                'electrolyte_decomposition': 80.0,
                'gas_generation': 90.0,
                'internal_short': 45.0
            }[degradation_mode]

            soh_mean = base_soh + (np.random.random() - 0.5) * 5  # Add some variance
            soh_var = np.random.random() * 4 + 1  # Variance between 1 and 5

            # Determine system state based on confidence
            if degradation_prob < 0.6:
                system_state = SystemState.RESENSING
            elif degradation_prob < 0.8:
                system_state = SystemState.ANALYZING
            else:
                system_state = SystemState.REBALANCING

            # Simulate confidence weights for modalities (would come from uncertainty heads in real model)
            # These represent the precision (inverse variance) from each modality
            if degradation_mode == 'healthy':
                precisions = {'electrical': 0.8, 'ultrasonic': 0.7, 'thermal': 0.6}
            elif degradation_mode == 'li_plating':
                precisions = {'electrical': 0.9, 'ultrasonic': 0.5, 'thermal': 0.4}
            elif degradation_mode == 'active_material_loss':
                precisions = {'electrical': 0.6, 'ultrasonic': 0.8, 'thermal': 0.7}
            elif degradation_mode == 'electrolyte_decomposition':
                precisions = {'electrical': 0.7, 'ultrasonic': 0.6, 'thermal': 0.9}
            elif degradation_mode == 'gas_generation':
                precisions = {'electrical': 0.5, 'ultrasonic': 0.4, 'thermal': 0.8}
            else:  # internal_short
                precisions = {'electrical': 0.4, 'ultrasonic': 0.3, 'thermal': 0.9}

            # Normalize to get confidence weights
            total_precision = sum(precisions.values())
            confidences = {k: v/total_precision for k, v in precisions.items()}

            # Store results in session state for persistence between runs
            st.session_state['last_results'] = {
                'results': results,
                'processed': processed,
                'mode_idx': mode_idx,
                'degradation_prob': degradation_prob,
                'soh_mean': soh_mean,
                'soh_var': soh_var,
                'system_state': system_state,
                'confidences': confidences,
                'timestamp': datetime.now()
            }

    # Display results if available
    if 'last_results' in st.session_state:
        data = st.session_state['last_results']
        results = data['results']
        processed = data['processed']
        mode_idx = data['mode_idx']
        degradation_prob = data['degradation_prob']
        soh_mean = data['soh_mean']
        soh_var = data['soh_var']
        system_state = data['system_state']
        confidences = data['confidences']
        timestamp = data['timestamp']

        # Header with timestamp and degradation mode
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.caption(f"Last updated: {timestamp.strftime('%H:%M:%S')}")
        with col2:
            mode_names = ['Healthy', 'Li Plating', 'Active Material Loss',
                         'Electrolyte Decomposition', 'Gas Generation', 'Internal Short']
            st.caption(f"Degradation Mode: {mode_names[mode_idx]}")
        with col3:
            st.caption(f"Classification Confidence: {degradation_prob:.1%}")

        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Signals & Diagnostics", "📈 Confidence Analysis", "📋 Raw Data"])

        with tab1:
            # Signal plots
            st.plotly_chart(create_signal_plots(
                results['electrical'],
                results['ultrasonic'],
                results['thermal'],
                results['electrical']['time']
            ), use_container_width=True)

            # SOH gauge and decision engine output in columns
            col1, col2 = st.columns([1, 1])

            with col1:
                st.plotly_chart(create_soh_gauge(soh_mean, soh_var), use_container_width=True)

            with col2:
                # Decision engine output
                engine = DecisionEngine()
                action, parameters = engine.decide(mode_idx, degradation_prob, soh_mean)

                st.subheader("🎯 Decision Engine Output")
                st.write(f"**System State:** {system_state.name}")
                st.write(f"**Recommended Action:** {engine.get_action_description(action)}")

                if action != engine.RecoveryAction.NONE and action != engine.RecoveryAction.RESENSING:
                    with st.expander("Action Parameters"):
                        for key, value in parameters.items():
                            st.write(f"• {key}: {value}")
                elif action == engine.RecoveryAction.RESENSING:
                    st.info("⚠️ Low confidence - requesting another sensing cycle")
                else:
                    st.info("✅ No action required - healthy cell or low confidence")

        with tab2:
            # Confidence analysis
            st.plotly_chart(create_confidence_bars(confidences), use_container_width=True)

            # Modality insights
            st.subheader("🔍 Modality Insights")
            sorted_confidences = sorted(confidences.items(), key=lambda x: x[1], reverse=True)

            for modality, confidence in sorted_confidences:
                modality_name = modality.capitalize()
                color = {'electrical': '#FF6B6B', 'ultrasonic': '#45B7D1', 'thermal': '#96CEB4'}[modality]
                st.markdown(f"<span style='color: {color}; font-weight: bold;'>{modality_name}</span>: {confidence:.1%} weight", unsafe_allow_html=True)

                # Add interpretation based on which modality is most confident
                if confidence > 0.5:
                    st.caption(f"→ {modality_name} signal is most reliable for this degradation mode")
                elif confidence < 0.2:
                    st.caption(f"→ {modality_name} signal is least reliable for this degradation mode")

            st.caption("""
            *Confidence-weighted attention dynamically adjusts modality weights based on
            estimated reliability (precision) from each sensor modality.*
            """)

        with tab3:
            # Show raw signal data in expandable sections
            with st.expander("📊 Electrical Signal Data"):
                df_electrical = pd.DataFrame({
                    'Time (s):': results['electrical']['time'],
                    'Voltage (V):': results['electrical']['voltage'],
                    'Current (A):': results['electrical']['current']
                })
                st.dataframe(df_electrical.head(10), use_container_width=True)
                st.caption(f"Showing first 10 of {len(results['electrical']['time'])} samples")

            with st.expander("📊 Ultrasonic Signal Data"):
                df_ultrasonic = pd.DataFrame({
                    'Time (s):': results['ultrasonic']['time'],
                    'Signal (V):': results['ultrasonic']['signal']
                })
                st.dataframe(df_ultrasonic.head(10), use_container_width=True)
                st.caption(f"ToF: {results['ultrasonic']['tof']*1e6:.2f} µs, Amplitude: {results['ultrasonic']['amplitude']:.3f}")
                st.caption(f"Showing first 10 of {len(results['ultrasonic']['time'])} samples")

            with st.expander("📊 Thermal Signal Data"):
                df_thermal = pd.DataFrame({
                    'Time (s):': results['thermal']['time'],
                    'Temperature Rise (K):': results['thermal']['temperature_rise'],
                    'dT/dt (K/s):': results['thermal']['dT_dt']
                })
                st.dataframe(df_thermal.head(10), use_container_width=True)
                st.caption(f"Showing first 10 of {len(results['thermal']['time'])} samples")

        # State machine indicator at the bottom
        st.divider()
        st.subheader("🔄 System State Machine")
        create_state_machine_indicator(system_state.name)

        # Auto-refresh option
        st.sidebar.divider()
        if st.sidebar.checkbox("🔄 Auto-refresh (every 2s)", value=False):
            time.sleep(2)
            st.rerun()

    else:
        # Show placeholder when no data available
        st.info("👈 Use the controls in the sidebar to run a diagnostic cycle")

        # Show example plots with placeholder data
        st.subheader("Example Diagnostic View")

        # Generate placeholder data
        time_s = np.linspace(0, 0.1, 1000)  # 100ms window
        electrical_v = np.random.normal(0, 0.1, len(time_s))  # Placeholder
        electrical_i = np.random.normal(0.5, 0.05, len(time_s))  # Placeholder
        ultrasonic_s = np.random.normal(0, 0.05, len(time_s))  # Placeholder
        thermal_t = np.random.normal(0.1, 0.02, len(time_s))  # Placeholder

        # Create mock results structure
        mock_results = {
            'electrical': {
                'voltage': electrical_v,
                'current': electrical_i,
                'time': time_s
            },
            'ultrasonic': {
                'signal': ultrasonic_s,
                'tof': 5e-6,
                'amplitude': 0.8,
                'phase_shift': 0.0
            },
            'thermal': {
                'temperature_rise': thermal_t,
                'dT_dt': np.gradient(thermal_t, time_s[1]-time_s[0]),
                'time': time_s
            }
        }

        st.plotly_chart(create_signal_plots(
            mock_results['electrical'],
            mock_results['ultrasonic'],
            mock_results['thermal'],
            time_s
        ), use_container_width=True)

        st.plotly_chart(create_confidence_bars(), use_container_width=True)

        st.plotly_chart(create_soh_gauge(85.0), use_container_width=True)

        st.subheader("System State Machine")
        create_state_machine_indicator("IDLE")

if __name__ == "__main__":
    main()