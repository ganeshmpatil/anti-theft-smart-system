import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../services/api_client.dart';
import '../services/alarm_service.dart';
import '../services/update_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _urlCtrl = TextEditingController(text: ApiClient.baseUrl);
  bool _saved = false;
  late bool _alarmEnabled;
  bool _checkingUpdate = false;

  @override
  void initState() {
    super.initState();
    _alarmEnabled = AlarmService().alarmEnabled;
  }

  Future<void> _save() async {
    await ApiClient.saveBaseUrl(_urlCtrl.text.trim());
    setState(() => _saved = true);
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _saved = false);
    });
  }

  Future<void> _toggleAlarm(bool value) async {
    await AlarmService().setAlarmEnabled(value);
    setState(() => _alarmEnabled = value);
  }

  Future<void> _checkForUpdate() async {
    if (kIsWeb) return;
    setState(() => _checkingUpdate = true);
    final update = await UpdateService.checkForUpdate();
    if (!mounted) return;
    setState(() => _checkingUpdate = false);

    if (update == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('App is up to date!')),
      );
      return;
    }

    showUpdateDialog(context, update);
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Server URL', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              hintText: 'http://10.0.2.2:8000/api/v1',
            ),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _save,
            child: Text(_saved ? 'Saved!' : 'Save'),
          ),
          const SizedBox(height: 24),
          const Divider(),
          const SizedBox(height: 16),
          SwitchListTile(
            title: const Text('Emergency Alarm'),
            subtitle: const Text(
              'Play loud alarm sound when intrusion is detected',
            ),
            secondary: Icon(
              _alarmEnabled ? Icons.alarm_on : Icons.alarm_off,
              color: _alarmEnabled ? Colors.red : null,
            ),
            value: _alarmEnabled,
            onChanged: _toggleAlarm,
          ),
          const SizedBox(height: 8),
          const Divider(),
          const SizedBox(height: 16),
          ListTile(
            leading: const Icon(Icons.system_update),
            title: const Text('Check for Updates'),
            subtitle: const Text('Download latest version from GitHub'),
            trailing: _checkingUpdate
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.chevron_right),
            onTap: _checkingUpdate ? null : _checkForUpdate,
          ),
          const SizedBox(height: 24),
          const Text(
            'For Android emulator use http://10.0.2.2:8000/api/v1\n'
            'For physical device use your PC\'s LAN IP.',
          ),
        ],
      ),
    );
  }
}

/// Shows the update available dialog with download progress.
void showUpdateDialog(BuildContext context, AppUpdate update) {
  showDialog(
    context: context,
    barrierDismissible: false,
    builder: (_) => _UpdateDialog(update: update),
  );
}

class _UpdateDialog extends StatefulWidget {
  final AppUpdate update;
  const _UpdateDialog({required this.update});

  @override
  State<_UpdateDialog> createState() => _UpdateDialogState();
}

class _UpdateDialogState extends State<_UpdateDialog> {
  bool _downloading = false;
  double _progress = 0;
  String? _error;

  Future<void> _startDownload() async {
    setState(() {
      _downloading = true;
      _progress = 0;
      _error = null;
    });

    final success = await UpdateService.downloadAndInstall(
      widget.update.downloadUrl,
      onProgress: (p) {
        if (mounted) setState(() => _progress = p);
      },
    );

    if (!mounted) return;

    if (!success) {
      setState(() {
        _downloading = false;
        _error = 'Failed to download or install update.';
      });
    }
    // If success, the OS installer takes over
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Update Available'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('New version: ${widget.update.version}'),
          if (widget.update.releaseNotes.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              widget.update.releaseNotes,
              style: Theme.of(context).textTheme.bodySmall,
              maxLines: 5,
              overflow: TextOverflow.ellipsis,
            ),
          ],
          if (_downloading) ...[
            const SizedBox(height: 16),
            LinearProgressIndicator(value: _progress),
            const SizedBox(height: 8),
            Text('${(_progress * 100).toStringAsFixed(0)}%',
                textAlign: TextAlign.center),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(_error!, style: const TextStyle(color: Colors.red)),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: _downloading ? null : () => Navigator.pop(context),
          child: const Text('Later'),
        ),
        FilledButton(
          onPressed: _downloading ? null : _startDownload,
          child: Text(_downloading ? 'Downloading...' : 'Update Now'),
        ),
      ],
    );
  }
}
