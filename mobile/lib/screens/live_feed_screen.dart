import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../services/api_client.dart';

class LiveFeedScreen extends StatefulWidget {
  final int deviceId;
  final String deviceUid;

  const LiveFeedScreen({
    super.key,
    required this.deviceId,
    required this.deviceUid,
  });

  @override
  State<LiveFeedScreen> createState() => _LiveFeedScreenState();
}

class _LiveFeedScreenState extends State<LiveFeedScreen> {
  WebSocketChannel? _channel;
  Uint8List? _currentFrame;
  bool _connecting = true;
  String? _error;
  int _frameCount = 0;
  DateTime? _startTime;

  @override
  void initState() {
    super.initState();
    _startLiveFeed();
  }

  Future<void> _startLiveFeed() async {
    setState(() {
      _connecting = true;
      _error = null;
    });

    // Send live_feed_start command to the edge device
    try {
      await ApiClient.post('/commands', {
        'device_id': widget.deviceId,
        'action': 'live_feed_start',
        'params': {'duration': 120, 'fps': 3, 'camera_id': 'cam_front'},
      });
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to start live feed: ${e.message}';
          _connecting = false;
        });
      }
      return;
    }

    // Connect WebSocket
    final wsBase = ApiClient.baseUrl
        .replaceFirst('http://', 'ws://')
        .replaceFirst('https://', 'wss://')
        .replaceFirst('/api/v1', '');
    final wsUrl = '$wsBase/api/v1/live/${widget.deviceUid}';

    try {
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _startTime = DateTime.now();

      setState(() => _connecting = false);

      _channel!.stream.listen(
        (data) {
          if (!mounted) return;
          if (data is List<int>) {
            setState(() {
              _currentFrame = Uint8List.fromList(data);
              _frameCount++;
            });
          } else if (data is String && data == 'ping') {
            // Server keepalive ping — ignore
          }
        },
        onError: (error) {
          if (mounted) {
            setState(() => _error = 'Connection error: $error');
          }
        },
        onDone: () {
          if (mounted) {
            setState(() => _error = 'Live feed ended');
          }
        },
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'WebSocket connection failed: $e';
          _connecting = false;
        });
      }
    }
  }

  Future<void> _stopLiveFeed() async {
    try {
      await ApiClient.post('/commands', {
        'device_id': widget.deviceId,
        'action': 'live_feed_stop',
        'params': {},
      });
    } catch (_) {}
    _channel?.sink.close();
  }

  String get _fps {
    if (_startTime == null || _frameCount == 0) return '0.0';
    final elapsed = DateTime.now().difference(_startTime!).inMilliseconds / 1000;
    if (elapsed <= 0) return '0.0';
    return ((_frameCount / elapsed)).toStringAsFixed(1);
  }

  @override
  void dispose() {
    _stopLiveFeed();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text('Live — ${widget.deviceUid}'),
        actions: [
          if (_currentFrame != null)
            Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Center(
                child: Text(
                  '$_fps fps | $_frameCount frames',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
              ),
            ),
        ],
      ),
      body: Center(
        child: _connecting
            ? const Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CircularProgressIndicator(color: Colors.white),
                  SizedBox(height: 16),
                  Text('Connecting to camera...',
                      style: TextStyle(color: Colors.white70)),
                ],
              )
            : _error != null
                ? Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.videocam_off,
                          color: Colors.white54, size: 64),
                      const SizedBox(height: 16),
                      Text(_error!,
                          style: const TextStyle(color: Colors.white70)),
                      const SizedBox(height: 24),
                      FilledButton.icon(
                        onPressed: _startLiveFeed,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  )
                : _currentFrame != null
                    ? Image.memory(
                        _currentFrame!,
                        gaplessPlayback: true,
                        fit: BoxFit.contain,
                      )
                    : const Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.videocam, color: Colors.white54, size: 64),
                          SizedBox(height: 16),
                          Text('Waiting for frames...',
                              style: TextStyle(color: Colors.white70)),
                        ],
                      ),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          _stopLiveFeed();
          Navigator.pop(context);
        },
        backgroundColor: Colors.red,
        child: const Icon(Icons.stop, color: Colors.white),
      ),
    );
  }
}
