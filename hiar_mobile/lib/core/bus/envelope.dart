import 'dart:convert';

/// Enveloppe WebSocket HIAR v1 conforme à hiar_contract_v1.json
class HiarEnvelope {
  final int v;
  final String type;
  final String? id;
  final String? topic;
  final int? ts;
  final int? seq;
  final String? corr;
  final int? qos;
  final bool? retain;
  final Map<String, dynamic>? payload;
  final String? deviceId;
  final String? role;
  final String? appVersion;
  final String? registryHash;
  final int? lastSeq;
  final String? token;
  final String? session;
  final int? serverTime;
  final bool? registryStale;
  final int? heartbeatS;
  final int? maxMsgBytes;
  final Map<String, dynamic>? granted;
  final int? replay;
  final String? code;
  final String? message;

  HiarEnvelope({
    this.v = 1,
    required this.type,
    this.id,
    this.topic,
    this.ts,
    this.seq,
    this.corr,
    this.qos,
    this.retain,
    this.payload,
    this.deviceId,
    this.role,
    this.appVersion,
    this.registryHash,
    this.lastSeq,
    this.token,
    this.session,
    this.serverTime,
    this.registryStale,
    this.heartbeatS,
    this.maxMsgBytes,
    this.granted,
    this.replay,
    this.code,
    this.message,
  });

  factory HiarEnvelope.fromJson(Map<String, dynamic> json) {
    return HiarEnvelope(
      v: json['v'] as int? ?? 1,
      type: json['type'] as String,
      id: json['id'] as String?,
      topic: json['topic'] as String?,
      ts: json['ts'] as int?,
      seq: json['seq'] as int?,
      corr: json['corr'] as String?,
      qos: json['qos'] as int?,
      retain: json['retain'] as bool?,
      payload: json['payload'] as Map<String, dynamic>?,
      deviceId: json['device_id'] as String?,
      role: json['role'] as String?,
      appVersion: json['app_version'] as String?,
      registryHash: json['registry_hash'] as String?,
      lastSeq: json['last_seq'] as int?,
      token: json['token'] as String?,
      session: json['session'] as String?,
      serverTime: json['server_time'] as int?,
      registryStale: json['registry_stale'] as bool?,
      heartbeatS: json['heartbeat_s'] as int?,
      maxMsgBytes: json['max_msg_bytes'] as int?,
      granted: json['granted'] as Map<String, dynamic>?,
      replay: json['replay'] as int?,
      code: json['code'] as String?,
      message: json['message'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'v': v,
      'type': type,
    };
    if (id != null) map['id'] = id;
    if (topic != null) map['topic'] = topic;
    if (ts != null) map['ts'] = ts;
    if (seq != null) map['seq'] = seq;
    if (corr != null) map['corr'] = corr;
    if (qos != null) map['qos'] = qos;
    if (retain != null) map['retain'] = retain;
    if (payload != null) map['payload'] = payload;
    if (deviceId != null) map['device_id'] = deviceId;
    if (role != null) map['role'] = role;
    if (appVersion != null) map['app_version'] = appVersion;
    if (registryHash != null) map['registry_hash'] = registryHash;
    if (lastSeq != null) map['last_seq'] = lastSeq;
    if (token != null) map['token'] = token;
    if (session != null) map['session'] = session;
    if (serverTime != null) map['server_time'] = serverTime;
    if (registryStale != null) map['registry_stale'] = registryStale;
    if (heartbeatS != null) map['heartbeat_s'] = heartbeatS;
    if (maxMsgBytes != null) map['max_msg_bytes'] = maxMsgBytes;
    if (granted != null) map['granted'] = granted;
    if (replay != null) map['replay'] = replay;
    if (code != null) map['code'] = code;
    if (message != null) map['message'] = message;
    return map;
  }

  String encode() => json.encode(toJson());
}
