import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AlarmService {
  static final AlarmService _instance = AlarmService._();
  factory AlarmService() => _instance;
  AlarmService._();

  final AudioPlayer _player = AudioPlayer();
  bool _isPlaying = false;
  bool _alarmEnabled = true;

  bool get isPlaying => _isPlaying;
  bool get alarmEnabled => _alarmEnabled;

  Future<void> init() async {
    final prefs = await SharedPreferences.getInstance();
    _alarmEnabled = prefs.getBool('alarm_enabled') ?? true;

    // Set release mode so it uses the asset
    await _player.setReleaseMode(ReleaseMode.loop);
    await _player.setVolume(1.0);
  }

  Future<void> setAlarmEnabled(bool enabled) async {
    _alarmEnabled = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('alarm_enabled', enabled);
    if (!enabled && _isPlaying) {
      await stop();
    }
  }

  Future<void> play() async {
    if (!_alarmEnabled || _isPlaying || kIsWeb) return;
    try {
      _isPlaying = true;
      await _player.setVolume(1.0);
      await _player.setReleaseMode(ReleaseMode.loop);
      await _player.play(AssetSource('alarm_tone.wav'));
      debugPrint('[AlarmService] Alarm started');
    } catch (e) {
      _isPlaying = false;
      debugPrint('[AlarmService] Failed to play alarm: $e');
    }
  }

  Future<void> stop() async {
    if (!_isPlaying) return;
    try {
      await _player.stop();
      _isPlaying = false;
      debugPrint('[AlarmService] Alarm stopped');
    } catch (e) {
      debugPrint('[AlarmService] Failed to stop alarm: $e');
    }
  }
}
