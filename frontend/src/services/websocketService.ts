import { AppDispatch, RootState } from '../store';
import { DiagnosticFrame } from '../store/diagnosticFrameSlice';

/**
 * WebSocket service for connecting to the backend and receiving DiagnosticFrame streams
 */
class WebSocketService {
  private ws: WebSocket | null = null;
  private dispatch: AppDispatch | null = null;
  private reconnectInterval: number = 3000; // 3 seconds
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private isConnecting: boolean = false;

  /**
   * Initialize the WebSocket service with Redux dispatch
   * @param dispatch Redux dispatch function
   */
  init(dispatch: AppDispatch) {
    this.dispatch = dispatch;
    this.connect();
  }

  /**
   * Connect to the WebSocket server
   */
  private connect() {
    if (this.isConnecting) return;
    this.isConnecting = true;

    const wsUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws';

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        if (this.dispatch) {
          this.dispatch({ type: 'diagnosticFrame/setLoading', payload: false });
          this.dispatch({ type: 'diagnosticFrame/setError', payload: null });
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data: DiagnosticFrame = JSON.parse(event.data);
          if (this.dispatch) {
            this.dispatch({ type: 'diagnosticFrame/setFrame', payload: data });
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.isConnecting = false;
        if (this.dispatch) {
          this.dispatch({ type: 'diagnosticFrame/setLoading', payload: true });
          this.dispatch({ type: 'diagnosticFrame/setError', payload: 'WebSocket disconnected' });
        }
        // Attempt to reconnect
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        if (this.dispatch) {
          this.dispatch({ type: 'diagnosticFrame/setError', payload: 'WebSocket error' });
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.isConnecting = false;
      if (this.dispatch) {
        this.dispatch({ type: 'diagnosticFrame/setError', payload: 'Failed to connect to WebSocket' });
      }
      this.scheduleReconnect();
    }
  }

  /**
   * Schedule a reconnection attempt
   */
  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  /**
   * Send a message through the WebSocket
   * @param data Data to send
   */
  send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * Disconnect from the WebSocket server
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnecting = false;
    this.reconnectAttempts = 0;
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Create a singleton instance
const websocketService = new WebSocketService();
export default websocketService;