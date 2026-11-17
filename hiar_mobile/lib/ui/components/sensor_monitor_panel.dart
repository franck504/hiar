import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../theme/hiar_colors.dart';

/// Panneau moniteur temps réel du cycle de vie des capteurs, de l'ESP32,
/// des nœuds ROS 2 et du LLM dans le popup Paramètres.
class SensorMonitorPanel extends StatelessWidget {
  final ValueListenable<Map<String, dynamic>?> diagnosticsListenable;
  final ValueListenable<bool> connectedListenable;
  final VoidCallback? onRefresh;

  const SensorMonitorPanel({
    super.key,
    required this.diagnosticsListenable,
    required this.connectedListenable,
    this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: connectedListenable,
      builder: (context, isConnected, _) {
        return ValueListenableBuilder<Map<String, dynamic>?>(
          valueListenable: diagnosticsListenable,
          builder: (context, diag, _) {
            final esp32 = _asMap(diag?['esp32']);
            final sensors = _asMap(diag?['sensors']);
            final rosNodes = _asMap(diag?['ros_nodes']);
            final llm = _asMap(diag?['llm']);
            final fwMode = diag?['firmware_diagnostics']?.toString() ?? 'unknown';

            final cards = <_MonitorItem>[
              _buildItem(
                icon: Icons.memory,
                label: "ESP32 (USB)",
                data: esp32,
                isConnected: isConnected,
                offlineDetail: "Pi déconnecté",
              ),
              _buildItem(
                icon: Icons.sensors,
                label: "Ultrason HC-SR04",
                data: _asMap(sensors['ultrasonic']),
                isConnected: isConnected,
                offlineDetail: "En attente",
              ),
              _buildItem(
                icon: Icons.arrow_back_rounded,
                label: "IR Gauche",
                data: _asMap(sensors['ir_left']),
                isConnected: isConnected,
                offlineDetail: "En attente",
              ),
              _buildItem(
                icon: Icons.arrow_forward_rounded,
                label: "IR Droite",
                data: _asMap(sensors['ir_right']),
                isConnected: isConnected,
                offlineDetail: "En attente",
              ),
              _buildItem(
                icon: Icons.thermostat,
                label: "Temp. DS18B20",
                data: _asMap(sensors['ds18b20']),
                isConnected: isConnected,
                offlineDetail: "En attente",
              ),
              _buildItem(
                icon: Icons.favorite_outline,
                label: "Pouls MAX30102",
                data: _asMap(sensors['max30102']),
                isConnected: isConnected,
                offlineDetail: "En attente",
              ),
              _buildItem(
                icon: Icons.hub_outlined,
                label: "Nœuds ROS 2",
                data: rosNodes,
                isConnected: isConnected,
                offlineDetail: "Pi déconnecté",
              ),
              _buildItem(
                icon: Icons.psychology_outlined,
                label: "IA / LLM Qwen",
                data: llm,
                isConnected: isConnected,
                offlineDetail: "Pi déconnecté",
              ),
            ];

            final fwBadge = !isConnected
                ? "Hors ligne"
                : (fwMode == 'option_b'
                    ? "Sonde live"
                    : (fwMode == 'legacy_status' ? "Standard" : "En attente"));

            return Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: HiarColors.brume,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: HiarColors.border),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.monitor_heart_outlined, size: 16, color: HiarColors.azur),
                      const SizedBox(width: 6),
                      const Expanded(
                        child: Text(
                          "Moniteur système & capteurs",
                          style: TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w700,
                            color: HiarColors.marine,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: HiarColors.azurSoft,
                          borderRadius: BorderRadius.circular(99),
                        ),
                        child: Text(
                          fwBadge,
                          style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w600,
                            color: HiarColors.azurDark,
                          ),
                        ),
                      ),
                      if (onRefresh != null) ...[
                        const SizedBox(width: 4),
                        InkWell(
                          onTap: isConnected ? onRefresh : null,
                          borderRadius: BorderRadius.circular(8),
                          child: Padding(
                            padding: const EdgeInsets.all(4),
                            child: Icon(
                              Icons.refresh_rounded,
                              size: 16,
                              color: isConnected ? HiarColors.azur : HiarColors.text2.withOpacity(0.4),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 8),
                  LayoutBuilder(
                    builder: (context, constraints) {
                      final halfWidth = (constraints.maxWidth - 6) / 2;
                      return Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: cards.map((item) {
                          return SizedBox(
                            width: halfWidth > 140 ? halfWidth : constraints.maxWidth,
                            child: _SensorCard(item: item),
                          );
                        }).toList(),
                      );
                    },
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    return const {};
  }

  _MonitorItem _buildItem({
    required IconData icon,
    required String label,
    required Map<String, dynamic> data,
    required bool isConnected,
    required String offlineDetail,
  }) {
    if (!isConnected) {
      return _MonitorItem(
        icon: icon,
        label: label,
        status: 'offline',
        statusText: 'Hors ligne',
        detail: offlineDetail,
      );
    }
    if (data.isEmpty) {
      return _MonitorItem(
        icon: icon,
        label: label,
        status: 'unknown',
        statusText: 'Attente',
        detail: 'Récupération…',
      );
    }

    final status = (data['status']?.toString() ?? 'unknown').toLowerCase();
    final detail = data['detail']?.toString() ?? '—';

    final String statusText;
    switch (status) {
      case 'ok':
        statusText = 'Actif';
        break;
      case 'warn':
        statusText = 'Alerte';
        break;
      case 'absent':
        statusText = 'Absent';
        break;
      case 'offline':
        statusText = 'Hors ligne';
        break;
      default:
        statusText = 'Inconnu';
    }

    return _MonitorItem(
      icon: icon,
      label: label,
      status: status,
      statusText: statusText,
      detail: detail,
    );
  }
}

class _MonitorItem {
  final IconData icon;
  final String label;
  final String status;
  final String statusText;
  final String detail;

  const _MonitorItem({
    required this.icon,
    required this.label,
    required this.status,
    required this.statusText,
    required this.detail,
  });
}

class _SensorCard extends StatelessWidget {
  final _MonitorItem item;
  const _SensorCard({required this.item});

  @override
  Widget build(BuildContext context) {
    Color fg;
    Color bg;
    switch (item.status) {
      case 'ok':
        fg = HiarColors.ok;
        bg = HiarColors.okBg;
        break;
      case 'warn':
        fg = HiarColors.wait;
        bg = HiarColors.waitBg;
        break;
      case 'absent':
      case 'offline':
        fg = HiarColors.err;
        bg = HiarColors.errBg;
        break;
      default:
        fg = HiarColors.text2;
        bg = HiarColors.border.withOpacity(0.5);
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: HiarColors.card,
        borderRadius: BorderRadius.circular(9),
        border: Border.all(color: fg.withOpacity(0.28)),
      ),
      child: Row(
        children: [
          Container(
            width: 26,
            height: 26,
            decoration: BoxDecoration(
              color: bg,
              borderRadius: BorderRadius.circular(7),
            ),
            child: Icon(item.icon, size: 15, color: fg),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        item.label,
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: HiarColors.marine,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        color: fg,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 1),
                Text(
                  "${item.statusText} · ${item.detail}",
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w500,
                    color: item.status == 'ok' ? HiarColors.text2 : fg,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
