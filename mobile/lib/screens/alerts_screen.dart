import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import '../models/alert.dart';
import '../services/api_client.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  List<Alert> _alerts = [];
  bool _loading = true;
  bool _loadingMore = false;
  String? _error;
  int _offset = 0;
  static const _limit = 50;
  bool _hasMore = false;

  @override
  void initState() {
    super.initState();
    _loadAlerts();
  }

  Future<void> _loadAlerts({bool refresh = false}) async {
    if (refresh) {
      _offset = 0;
      _hasMore = true;
    }
    if (!refresh && _loadingMore) return;
    setState(() {
      if (refresh) {
        _loading = true;
        _error = null;
      } else {
        _loadingMore = true;
      }
    });
    try {
      final data =
          await ApiClient.get('/alerts?limit=$_limit&offset=$_offset');
      final newAlerts =
          (data as List).map((a) => Alert.fromJson(a)).toList();
      setState(() {
        if (refresh) {
          _alerts = newAlerts;
        } else {
          _alerts.addAll(newAlerts);
        }
        _hasMore = newAlerts.length == _limit;
        _offset += newAlerts.length;
        _loading = false;
        _loadingMore = false;
      });
    } catch (e) {
      setState(() {
        _error = e is ApiException ? e.message : 'Failed to load alerts';
        _loading = false;
        _loadingMore = false;
      });
    }
  }

  Future<void> _clearAllAlerts() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Clear All Alerts'),
        content: const Text(
            'This will permanently delete all alerts. This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Clear All'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    try {
      await ApiClient.delete('/alerts');
      if (mounted) {
        setState(() {
          _alerts = [];
          _offset = 0;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('All alerts cleared')),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _acknowledgeAlert(Alert alert) async {
    try {
      await ApiClient.patch('/alerts/${alert.id}/ack', {
        'acknowledged': true,
      });
      _loadAlerts(refresh: true);
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    }
  }

  Future<void> _showSuspendDialog(Alert alert) async {
    final durations = [
      {'label': '15 minutes', 'minutes': 15},
      {'label': '30 minutes', 'minutes': 30},
      {'label': '1 hour', 'minutes': 60},
      {'label': '2 hours', 'minutes': 120},
      {'label': '4 hours', 'minutes': 240},
      {'label': '8 hours', 'minutes': 480},
      {'label': '24 hours', 'minutes': 1440},
    ];

    if (!mounted) return;
    final selected = await showDialog<int>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Suspend Alerts'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Pause alerts for Device #${alert.deviceId}.\n'
              'You will not receive notifications during this time.',
              style: Theme.of(dialogContext).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            ...durations.map((d) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.timer),
                  title: Text(d['label'] as String),
                  onTap: () =>
                      Navigator.pop(dialogContext, d['minutes'] as int),
                )),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Cancel'),
          ),
        ],
      ),
    );

    if (selected == null || !mounted) return;

    try {
      await ApiClient.put(
        '/devices/${alert.deviceId}/suspend',
        {'duration_minutes': selected},
      );
      if (mounted) {
        final label = durations
            .firstWhere((d) => d['minutes'] == selected)['label'];
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Alerts suspended for $label'),
            action: SnackBarAction(
              label: 'Undo',
              onPressed: () => _resumeAlerts(alert.deviceId),
            ),
          ),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _resumeAlerts(int deviceId) async {
    try {
      await ApiClient.put(
        '/devices/$deviceId/suspend',
        {'duration_minutes': 0},
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Alerts resumed')),
        );
      }
    } on ApiException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.message), backgroundColor: Colors.red),
        );
      }
    }
  }

  Future<void> _showAlertImage(Alert alert) async {
    if (alert.imagePath == null || alert.imagePath!.isEmpty) return;

    final token = await ApiClient.getToken();
    final url =
        '${ApiClient.baseUrl.replaceFirst('/api/v1', '')}/api/v1/alerts/${alert.id}/image';

    if (!mounted) return;
    showDialog(
      context: context,
      builder: (dialogContext) => Dialog(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AppBar(
              title: Text('Alert #${alert.id}'),
              automaticallyImplyLeading: false,
              actions: [
                IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(dialogContext)),
              ],
            ),
            FutureBuilder<http.Response>(
              future: http.get(Uri.parse(url), headers: {
                if (token != null) 'Authorization': 'Bearer $token',
              }),
              builder: (_, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Padding(
                    padding: EdgeInsets.all(32),
                    child: CircularProgressIndicator(),
                  );
                }
                if (snapshot.hasError ||
                    snapshot.data == null ||
                    snapshot.data!.statusCode != 200) {
                  return const Padding(
                    padding: EdgeInsets.all(32),
                    child: Text('Failed to load image'),
                  );
                }
                return Image.memory(
                    Uint8List.fromList(snapshot.data!.bodyBytes));
              },
            ),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Type: ${alert.alertType}'),
                  Text(
                      'Confidence: ${(alert.confidence * 100).toStringAsFixed(1)}%'),
                  Text('Time: ${alert.createdAt}'),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _showAlertVideo(Alert alert) async {
    if (!alert.hasVideo) return;

    final token = await ApiClient.getToken();
    final url =
        '${ApiClient.baseUrl.replaceFirst('/api/v1', '')}/api/v1/alerts/${alert.id}/video';

    if (!mounted) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => _VideoPlayerScreen(
          alertId: alert.id,
          videoUrl: url,
          authToken: token,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Alerts'),
        actions: [
          if (_alerts.isNotEmpty)
            IconButton(
              icon: const Icon(Icons.delete_sweep),
              tooltip: 'Clear all alerts',
              onPressed: _clearAllAlerts,
            ),
        ],
      ),
      body: _loading && _alerts.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : _error != null && _alerts.isEmpty
              ? Center(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(_error!,
                          style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: () => _loadAlerts(refresh: true),
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: () => _loadAlerts(refresh: true),
                  child: _alerts.isEmpty
                      ? const Center(child: Text('No alerts'))
                      : ListView.builder(
                          itemCount: _alerts.length + (_hasMore ? 1 : 0),
                          itemBuilder: (_, i) {
                            if (i == _alerts.length) {
                              if (!_loadingMore) {
                                WidgetsBinding.instance
                                    .addPostFrameCallback((_) {
                                  _loadAlerts();
                                });
                              }
                              return const Padding(
                                padding: EdgeInsets.all(16),
                                child: Center(
                                    child: CircularProgressIndicator()),
                              );
                            }
                            final a = _alerts[i];
                            return Card(
                              margin: const EdgeInsets.symmetric(
                                  horizontal: 16, vertical: 4),
                              color: a.acknowledged
                                  ? null
                                  : Theme.of(context)
                                      .colorScheme
                                      .errorContainer,
                              child: ListTile(
                                leading: Icon(
                                  Icons.warning_amber,
                                  color: a.acknowledged
                                      ? Colors.grey
                                      : Colors.red,
                                  size: 32,
                                ),
                                title: Text(
                                    '${a.alertType} — ${(a.confidence * 100).toStringAsFixed(0)}%'),
                                subtitle: Text(
                                    'Device #${a.deviceId} • ${a.createdAt}'),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    if (a.imagePath != null &&
                                        a.imagePath!.isNotEmpty)
                                      IconButton(
                                        icon: const Icon(Icons.image),
                                        tooltip: 'View snapshot',
                                        onPressed: () =>
                                            _showAlertImage(a),
                                      ),
                                    if (a.hasVideo)
                                      IconButton(
                                        icon: const Icon(
                                            Icons.play_circle_outline),
                                        tooltip: 'Play video clip',
                                        onPressed: () =>
                                            _showAlertVideo(a),
                                      ),
                                    if (!a.acknowledged)
                                      IconButton(
                                        icon: const Icon(Icons.snooze),
                                        tooltip: 'Suspend alerts',
                                        onPressed: () =>
                                            _showSuspendDialog(a),
                                      ),
                                    if (!a.acknowledged)
                                      IconButton(
                                        icon: const Icon(Icons.check),
                                        tooltip: 'Acknowledge',
                                        onPressed: () =>
                                            _acknowledgeAlert(a),
                                      ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                ),
    );
  }
}

class _VideoPlayerScreen extends StatefulWidget {
  final int alertId;
  final String videoUrl;
  final String? authToken;

  const _VideoPlayerScreen({
    required this.alertId,
    required this.videoUrl,
    this.authToken,
  });

  @override
  State<_VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<_VideoPlayerScreen> {
  VideoPlayerController? _videoController;
  ChewieController? _chewieController;
  bool _loading = true;
  String? _error;
  File? _tempFile;

  @override
  void initState() {
    super.initState();
    _loadVideo();
  }

  Future<void> _loadVideo() async {
    try {
      // Download video bytes with auth header
      final response = await http.get(
        Uri.parse(widget.videoUrl),
        headers: {
          if (widget.authToken != null)
            'Authorization': 'Bearer ${widget.authToken}',
        },
      );

      if (response.statusCode != 200) {
        setState(() {
          _error = 'Failed to load video (${response.statusCode})';
          _loading = false;
        });
        return;
      }

      // Write to temp file (video_player needs a file or network URL)
      final tempDir = await getTemporaryDirectory();
      final file = File('${tempDir.path}/alert_${widget.alertId}.mp4');
      await file.writeAsBytes(response.bodyBytes);
      _tempFile = file;

      final controller = VideoPlayerController.file(file);
      await controller.initialize();

      if (!mounted) {
        controller.dispose();
        return;
      }

      _videoController = controller;
      _chewieController = ChewieController(
        videoPlayerController: controller,
        autoPlay: true,
        looping: false,
        showControlsOnInitialize: true,
        aspectRatio: controller.value.aspectRatio,
      );

      setState(() => _loading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Failed to load video: $e';
          _loading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _chewieController?.dispose();
    _videoController?.dispose();
    _tempFile?.delete().catchError((_) => _tempFile!);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Alert #${widget.alertId} — Video')),
      backgroundColor: Colors.black,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      _error!,
                      style: const TextStyle(color: Colors.red),
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              : Center(
                  child: Chewie(controller: _chewieController!),
                ),
    );
  }
}
