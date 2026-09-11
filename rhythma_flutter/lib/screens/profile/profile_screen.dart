import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:path_provider/path_provider.dart';
import 'package:path/path.dart' as p;
import 'package:provider/provider.dart';
import '../../components/shared.dart';
import '../../config/theme.dart';
import '../../services/api_client.dart';
import '../../services/local_storage_service.dart';
import '../settings/settings_screen.dart';
import 'package:rhythma/l10n/app_localizations.dart';
import 'package:url_launcher/url_launcher_string.dart';
import '../../providers/theme_provider.dart';
import '../../providers/profile_provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  String _userName = 'Aarya';
  int _userAge = 28;
  int _cycleLength = 28;
  final int _cycleDay = 12;

  double? _avgCycleFromApi;
  double? _avgBleeding;
  List<int> _cycleHistory = [];

  List<Map<String, String>> _emergencyContacts = [];

  @override
  void initState() {
    super.initState();
    _loadProfile();
    _loadEmergencyContacts();
    _fetchDashboardInsights();
  }

  void _loadProfile() {
    final profile = LocalStorageService.getProfile();
    if (profile != null) {
      _userName = profile['name'] as String? ?? 'Aarya';
      _userAge = profile['age'] as int? ?? 28;
      _cycleLength = profile['cycle_length'] as int? ?? 28;
    }
  }

  void _loadEmergencyContacts() {
    _emergencyContacts = LocalStorageService.getEmergencyContacts();
  }

  Future<void> _fetchDashboardInsights() async {
    try {
      final response = await ApiClient.dio.get('/dashboard');
      final data = response.data as Map;
      final insights = data['insights'] as Map? ?? {};
      final history = data['cycleHistory'] as List? ?? [];
      if (!mounted) return;
      setState(() {
        _avgCycleFromApi = (insights['averageCycleLength'] as num?)?.toDouble();
        _avgBleeding = (insights['averageBleedingDuration'] as num?)?.toDouble();
        _cycleHistory = history
            .map((e) => (e as Map)['cycle_length'])
            .whereType<num>()
            .map((n) => n.toInt())
            .toList();
      });
    } catch (_) {}
  }

  String _getCyclePhase(int day) {
    if (day <= 5) return 'Menstrual Phase';
    if (day <= 13) return 'Follicular Phase';
    if (day == 14) return 'Ovulation Phase';
    return 'Luteal Phase';
  }

  void _showEditProfileSheet() {
    final profile = context.read<ProfileProvider>().profile;
    String selectedAvatar = profile['avatar'] as String? ?? '';
    if (selectedAvatar.isNotEmpty && !selectedAvatar.startsWith('/') && !selectedAvatar.startsWith('assets/')) {
      selectedAvatar = '';
    }

    final nameController = TextEditingController(text: _userName);
    final ageController = TextEditingController(text: _userAge.toString());
    final cycleController = TextEditingController(text: _cycleLength.toString());

    String? nameError;
    String? ageError;
    String? cycleError;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Container(
            decoration: BoxDecoration(
              color: RhythmaColors.surface,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SectionHeader(title: AppLocalizations.of(context)!.profileEditProfile),
                const SizedBox(height: 16),
                Text(
                  AppLocalizations.of(context)!.onboardingAvatarLabel,
                  style: TextStyle(fontSize: 14, color: RhythmaColors.mutedFg),
                ),
                const SizedBox(height: 8),
                GestureDetector(
                  onTap: () async {
                    final picker = ImagePicker();
                    final picked = await picker.pickImage(
                      source: ImageSource.gallery,
                      maxWidth: 512,
                      maxHeight: 512,
                      imageQuality: 85,
                    );
                    if (picked != null) {
                      final appDir = await getApplicationDocumentsDirectory();
                      final fileName = 'avatar_${DateTime.now().millisecondsSinceEpoch}${p.extension(picked.path)}';
                      final savedFile = await File(picked.path).copy('${appDir.path}/$fileName');
                      setSheetState(() => selectedAvatar = savedFile.path);
                    }
                  },
                  child: Container(
                    width: 68,
                    height: 68,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: selectedAvatar.isNotEmpty
                          ? RhythmaColors.primary.withValues(alpha: 0.1)
                          : RhythmaColors.surfaceMuted,
                      border: Border.all(
                        color: selectedAvatar.isNotEmpty
                            ? RhythmaColors.primary
                            : RhythmaColors.border,
                        width: 2,
                      ),
                    ),
                    child: selectedAvatar.isNotEmpty
                        ? ClipOval(
                            child: selectedAvatar.startsWith('/')
                                ? Image.file(
                                    File(selectedAvatar),
                                    width: 68,
                                    height: 68,
                                    fit: BoxFit.cover,
                                  )
                                : Image.asset(
                                    selectedAvatar,
                                    width: 68,
                                    height: 68,
                                    fit: BoxFit.cover,
                                  ),
                          )
                        : Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.camera_alt_rounded,
                                  color: RhythmaColors.mutedFg, size: 20),
                              const SizedBox(height: 2),
                              Text(
                                'Pick',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: RhythmaColors.mutedFg,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ],
                          ),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: nameController,
                  decoration: InputDecoration(
                    labelText: AppLocalizations.of(context)!.profileName,
                    errorText: nameError,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: ageController,
                  decoration: InputDecoration(
                    labelText: AppLocalizations.of(context)!.profileAge,
                    errorText: ageError,
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: cycleController,
                  decoration: InputDecoration(
                    labelText: AppLocalizations.of(context)!.profileAvgCycleDays,
                    errorText: cycleError,
                  ),
                  keyboardType: TextInputType.number,
                ),
                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: () async {
                    setSheetState(() {
                      nameError = null;
                      ageError = null;
                      cycleError = null;
                    });

                    final name = nameController.text.trim();
                    final ageVal = int.tryParse(ageController.text);
                    final cycleVal = int.tryParse(cycleController.text);

                    bool isValid = true;

                    if (name.isEmpty) {
                      setSheetState(() => nameError = AppLocalizations.of(context)!.profileNameEmptyError);
                      isValid = false;
                    }

                    if (ageVal == null || ageVal < 10 || ageVal > 120) {
                      setSheetState(() => ageError = AppLocalizations.of(context)!.profileAgeInvalidError);
                      isValid = false;
                    }

                    if (cycleVal == null || cycleVal < 15 || cycleVal > 45) {
                      setSheetState(() => cycleError = AppLocalizations.of(context)!.profileCycleInvalidError);
                      isValid = false;
                    }

                    if (isValid) {
                      setState(() {
                        _userName = name;
                        _userAge = ageVal!;
                        _cycleLength = cycleVal!;
                      });
                      
                      await context.read<ProfileProvider>().mergeProfile({
                        'name': name,
                        'age': ageVal!,
                        'cycle_length': cycleVal!,
                        'avatar': selectedAvatar,
                      });

                      if (context.mounted) {
                        Navigator.pop(context);
                      }
                    }
                  },
                  child: Text(AppLocalizations.of(context)!.profileSaveChanges),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }

void _showAddEditContactDialog(
    int? editIndex,
    StateSetter setSheetState,
  ) {
    final contact =
        editIndex != null ? _emergencyContacts[editIndex] : null;

    final nameController =
        TextEditingController(text: contact?['name']);
    final phoneController =
        TextEditingController(text: contact?['phone']);

    String? nameError;
    String? phoneError;

    showDialog(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => Semantics(
          label: editIndex == null
              ? AppLocalizations.of(context)!.profileAddContact
              : AppLocalizations.of(context)!.profileEditContact,
          child: AlertDialog(
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
            ),
            title: Text(
              editIndex == null
                  ? AppLocalizations.of(context)!.profileAddContact
                  : AppLocalizations.of(context)!.profileEditContact,
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: nameController,
                  textInputAction: TextInputAction.next,
                  decoration: InputDecoration(
                    labelText:
                        AppLocalizations.of(context)!.profileName,
                    errorText: nameError,
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: phoneController,
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.done,
                  decoration: InputDecoration(
                    labelText:
                        AppLocalizations.of(context)!.profilePhone,
                    errorText: phoneError,
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text(AppLocalizations.of(context)!.cancel),
              ),
              ElevatedButton(
                onPressed: () async {
                  setDialogState(() {
                    nameError = null;
                    phoneError = null;
                  });

                  final name = nameController.text.trim();
                  final phone = phoneController.text.trim();

                  bool isValid = true;

                  if (name.isEmpty) {
                    setDialogState(() {
                      nameError = AppLocalizations.of(context)!
                          .contactNameRequiredError;
                    });
                    isValid = false;
                  }

                  if (phone.isEmpty ||
                      phone.length < 8 ||
                      !RegExp(r'^\+?[0-9\s\-]+$').hasMatch(phone)) {
                    setDialogState(() {
                      phoneError = AppLocalizations.of(context)!
                          .profilePhoneInvalidError;
                    });
                    isValid = false;
                  }

                  if (!isValid) return;

                  setSheetState(() {
                    if (editIndex == null) {
                      _emergencyContacts.add({
                        'name': name,
                        'phone': phone,
                      });
                    } else {
                      _emergencyContacts[editIndex] = {
                        'name': name,
                        'phone': phone,
                      };
                    }
                  });

                  await LocalStorageService.saveEmergencyContacts(
                    _emergencyContacts,
                  );

                  if (context.mounted) {
                    Navigator.pop(context);
                  }
                },
                child: Text(
                  AppLocalizations.of(context)!.profileSave,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  void _showEmergencyContactsSheet() {
  showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) => StatefulBuilder(
      builder: (context, setSheetState) {
        final contacts = _emergencyContacts;
        
        return Padding(
          padding: EdgeInsets.only(
            bottom: MediaQuery.of(context).viewInsets.bottom,
          ),
          child: Container(
            decoration: BoxDecoration(
              color: RhythmaColors.surface,
              borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
            ),
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SectionHeader(
                  title: AppLocalizations.of(context)!.profileEmergencyContactsTitle,
                  action: AppLocalizations.of(context)!.profileAddNew,
                  onAction: () {
                    _showAddEditContactDialog(null, setSheetState);
                  },
                ),
                const SizedBox(height: 12),
                if (contacts.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 32),
                    child: Text(
                      AppLocalizations.of(context)!.profileNoContacts,
                      textAlign: TextAlign.center,
                      style: TextStyle(color: RhythmaColors.mutedFg),
                    ),
                  )
                else
                  Flexible(
                    child: ListView.separated(
                      shrinkWrap: true,
                      itemCount: contacts.length,
                      separatorBuilder: (context, index) => Divider(
                        height: 1,
                        color: RhythmaColors.border,
                      ),
                      itemBuilder: (context, index) {
                        final contact = contacts[index];
                        return ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const TintedIcon(
                            icon: Icons.contact_phone_rounded,
                            color: RhythmaColors.rose,
                            size: 36,
                          ),
                          title: Text(
                            contact['name'] ?? '',
                            style: const TextStyle(fontWeight: FontWeight.w600),
                          ),
                          subtitle: Text(
                            contact['phone'] ?? '',
                            style: TextStyle(color: RhythmaColors.mutedFg),
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              IconButton(
                                icon: const Icon(Icons.phone_rounded, size: 20),
                                tooltip: 'Call',
                                onPressed: () {
                                  final phone = contact['phone']?.replaceAll(RegExp(r'[^\d+]'), '');
                                  if (phone != null && phone.isNotEmpty) {
                                    launchUrlString('tel:$phone');
                                  }
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.message_rounded, size: 20),
                                tooltip: 'SMS',
                                onPressed: () {
                                  final phone = contact['phone']?.replaceAll(RegExp(r'[^\d+]'), '');
                                  if (phone != null && phone.isNotEmpty) {
                                    launchUrlString('sms:$phone');
                                  }
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.edit_rounded, size: 20),
                                tooltip: AppLocalizations.of(context)!.edit,
                                onPressed: () {
                                  _showAddEditContactDialog(index, setSheetState);
                                },
                              ),
                              IconButton(
                                icon: const Icon(Icons.delete_outline_rounded,
                                    color: RhythmaColors.coral, size: 20),
                                tooltip: AppLocalizations.of(context)!.delete,
                                onPressed: () async {
                                  setSheetState(() {
                                    _emergencyContacts.removeAt(index);
                                  });
                                  await LocalStorageService.saveEmergencyContacts(_emergencyContacts);
                                },
                              ),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      },
    ),
  );
}

  void _showAvatarOptionsSheet() {
    final profile = context.read<ProfileProvider>().profile;
    final avatarPath = profile['avatar'] as String? ?? '';
    final hasAvatar = avatarPath.isNotEmpty;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      builder: (ctx) => Container(
        decoration: BoxDecoration(
          color: RhythmaColors.surface,
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
        ),
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: RhythmaColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 20),
            if (hasAvatar)
              ListTile(
                leading: TintedIcon(
                  icon: Icons.visibility_rounded,
                  color: RhythmaColors.primary,
                  size: 36,
                ),
                title: const Text('View Photo'),
                onTap: () {
                  Navigator.pop(ctx);
                  _viewAvatarFullScreen(avatarPath);
                },
              ),
            if (hasAvatar) Divider(height: 1, color: RhythmaColors.border),
            ListTile(
              leading: TintedIcon(
                icon: Icons.photo_library_rounded,
                color: RhythmaColors.teal,
                size: 36,
              ),
              title: Text(AppLocalizations.of(context)!.onboardingAvatarLabel),
              onTap: () async {
                Navigator.pop(ctx);
                try {
                  final picker = ImagePicker();
                  final picked = await picker.pickImage(
                    source: ImageSource.gallery,
                    maxWidth: 512,
                    maxHeight: 512,
                    imageQuality: 85,
                  );
                  if (picked != null && mounted) {
                    final appDir = await getApplicationDocumentsDirectory();
                    final ext = p.extension(picked.path);
                    final fileName = 'avatar_${DateTime.now().millisecondsSinceEpoch}$ext';
                    final savedFile = await File(picked.path).copy('${appDir.path}/$fileName');
                    if (mounted) {
                      await context.read<ProfileProvider>().mergeProfile({
                        'avatar': savedFile.path,
                      });
                      setState(() {});
                    }
                  }
                } catch (_) {}
              },
            ),
            Divider(height: 1, color: RhythmaColors.border),
            ListTile(
              leading: TintedIcon(
                icon: Icons.camera_alt_rounded,
                color: RhythmaColors.coral,
                size: 36,
              ),
              title: const Text('Take Photo'),
              onTap: () async {
                try {
                  final picker = ImagePicker();
                  final picked = await picker.pickImage(
                    source: ImageSource.camera,
                    maxWidth: 512,
                    maxHeight: 512,
                    imageQuality: 85,
                  );
                  if (picked != null && ctx.mounted) {
                    Navigator.pop(ctx);
                    final appDir = await getApplicationDocumentsDirectory();
                    final ext = p.extension(picked.path);
                    final fileName = 'avatar_${DateTime.now().millisecondsSinceEpoch}$ext';
                    final savedFile = await File(picked.path).copy('${appDir.path}/$fileName');
                    if (mounted) {
                      await context.read<ProfileProvider>().mergeProfile({
                        'avatar': savedFile.path,
                      });
                      setState(() {});
                    }
                  } else if (ctx.mounted) {
                    Navigator.pop(ctx);
                  }
                } catch (_) {
                  if (ctx.mounted) Navigator.pop(ctx);
                }
              },
            ),
            if (hasAvatar) ...[
              Divider(height: 1, color: RhythmaColors.border),
              ListTile(
                leading: const TintedIcon(
                  icon: Icons.delete_outline_rounded,
                  color: Colors.redAccent,
                  size: 36,
                ),
                title: const Text('Remove Photo',
                    style: TextStyle(color: Colors.redAccent)),
                onTap: () async {
                  Navigator.pop(ctx);
                  await context.read<ProfileProvider>().mergeProfile({
                    'avatar': '',
                  });
                  setState(() {});
                },
              ),
            ],
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  void _viewAvatarFullScreen(String avatarPath) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          backgroundColor: Colors.black,
          appBar: AppBar(
            backgroundColor: Colors.black,
            iconTheme: const IconThemeData(color: Colors.white),
          ),
          body: Center(
            child: avatarPath.startsWith('/')
                ? Image.file(File(avatarPath), fit: BoxFit.contain)
                : Image.asset(avatarPath, fit: BoxFit.contain),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final profile = context.read<ProfileProvider>().profile;
    String avatarPath = profile['avatar'] as String? ?? '';
    final bool hasAvatar = avatarPath.isNotEmpty;

    return Column(
      children: [
        InkWell(
          onTap: () => _showAvatarOptionsSheet(),
          borderRadius: BorderRadius.circular(56),
          child: Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RhythmaGradients.primary,
            ),
            child: Container(
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: RhythmaColors.background,
              ),
              child: CircleAvatar(
                radius: 42,
                backgroundColor: RhythmaColors.surfaceMuted,
                backgroundImage: hasAvatar
                    ? (avatarPath.startsWith('/')
                        ? FileImage(File(avatarPath))
                        : AssetImage(avatarPath) as ImageProvider)
                    : null,
                onBackgroundImageError: hasAvatar ? (_, __) {} : null,
                child: hasAvatar
                    ? null
                    : Icon(Icons.person_rounded,
                        size: 42, color: RhythmaColors.mutedFg),
              ),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.camera_alt_rounded, size: 12, color: RhythmaColors.mutedFg),
            const SizedBox(width: 2),
            Text(
              'Tap to change',
              style: TextStyle(fontSize: 10, color: RhythmaColors.mutedFg),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          _userName,
          style: TextStyle(
            fontSize: 22,
            fontWeight: FontWeight.w800,
            color: RhythmaColors.foreground,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          '$_userAge ${AppLocalizations.of(context)!.profileYearsOld}',
          style: TextStyle(fontSize: 13, color: RhythmaColors.mutedFg),
        ),
        const SizedBox(height: 6),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                RhythmaColors.teal.withValues(alpha: 0.15),
                RhythmaColors.teal.withValues(alpha: 0.08),
              ],
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: RhythmaColors.teal.withValues(alpha: 0.25),
              width: 0.8,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.water_drop, color: RhythmaColors.teal, size: 14),
              const SizedBox(width: 4),
              Text(
                '${AppLocalizations.of(context)!.profileCycleDay} $_cycleDay \u2022 ${_getCyclePhase(_cycleDay)}',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: RhythmaColors.teal,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildHealthSummary() {
    final avgCycle = _avgCycleFromApi ?? _cycleLength.toDouble();
    final bleeding = _avgBleeding;
    final cycleDay = _cycleDay;

    return GlassCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              TintedIcon(icon: Icons.monitor_heart_rounded, color: RhythmaColors.teal, size: 28),
              const SizedBox(width: 8),
              Text(
                'Health Summary',
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: RhythmaColors.foreground,
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              _buildMiniStat(
                icon: Icons.calendar_today_rounded,
                value: '${avgCycle.toStringAsFixed(avgCycle % 1 == 0 ? 0 : 1)}d',
                label: 'Avg Cycle',
                color: RhythmaColors.rose,
              ),
              const SizedBox(width: 12),
              _buildMiniStat(
                icon: Icons.water_drop_rounded,
                value: bleeding != null ? '${bleeding.toStringAsFixed(bleeding % 1 == 0 ? 0 : 1)}d' : '--',
                label: 'Avg Period',
                color: RhythmaColors.coral,
              ),
              const SizedBox(width: 12),
              _buildMiniStat(
                icon: Icons.today_rounded,
                value: '$cycleDay',
                label: 'Cycle Day',
                color: RhythmaColors.primary,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMiniStat({
    required IconData icon,
    required String value,
    required String label,
    required Color color,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          children: [
            Icon(icon, size: 18, color: color),
            const SizedBox(height: 4),
            Text(
              value,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: RhythmaColors.foreground,
              ),
            ),
            const SizedBox(height: 1),
            Text(
              label,
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w500,
                color: RhythmaColors.mutedFg,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard({
    required IconData icon,
    required Color color,
    required String value,
    required String label,
  }) {
    return GlassCard(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              TintedIcon(icon: icon, color: color, size: 28),
              Icon(
                Icons.trending_flat_rounded,
                color: color.withValues(alpha: 0.6),
                size: 16,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: RhythmaColors.foreground,
              height: 1.1,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            label,
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: RhythmaColors.mutedFg,
              height: 1.1,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }

  Widget _buildStatsCards() {
    final avgCycleDisplay = _avgCycleFromApi != null
        ? '${_avgCycleFromApi!.toStringAsFixed(_avgCycleFromApi! % 1 == 0 ? 0 : 1)} ${AppLocalizations.of(context)!.homeDaysLabel}'
        : '$_cycleLength ${AppLocalizations.of(context)!.homeDaysLabel}';
    final variability = _cycleHistory.length >= 2 ? _computeVariability(_cycleHistory) : 0;
    final variabilityDisplay = _cycleHistory.length >= 2 ? '$variability ${AppLocalizations.of(context)!.homeDaysLabel}' : '--';
    final lastCycleDisplay = _cycleHistory.isNotEmpty ? '${_cycleHistory.first} ${AppLocalizations.of(context)!.homeDaysLabel}' : '--';

    return Column(
      children: [
        Row(
          children: [
            Expanded(
              child: _buildStatCard(
                icon: Icons.calendar_month_rounded,
                color: RhythmaColors.rose,
                value: avgCycleDisplay,
                label: AppLocalizations.of(context)!.profileAvgCycleLength,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildStatCard(
                icon: Icons.water_drop_rounded,
                color: RhythmaColors.teal,
                value: _avgBleeding != null ? '${_avgBleeding!.toStringAsFixed(_avgBleeding! % 1 == 0 ? 0 : 1)}d' : '--',
                label: AppLocalizations.of(context)!.homeLogFlow,
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _buildStatCard(
                icon: Icons.insights_rounded,
                color: RhythmaColors.coral,
                value: variabilityDisplay,
                label: AppLocalizations.of(context)!.profileCycleVariability,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildStatCard(
                icon: Icons.history_toggle_off_rounded,
                color: RhythmaColors.primary,
                value: lastCycleDisplay,
                label: AppLocalizations.of(context)!.profileLastCycleLength,
              ),
            ),
          ],
        ),
      ],
    );
  }

  int _computeVariability(List<int> lengths) {
    if (lengths.length < 2) return 0;
    final mean = lengths.reduce((a, b) => a + b) / lengths.length;
    final variance =
        lengths.map((v) => (v - mean) * (v - mean)).reduce((a, b) => a + b) / lengths.length;
    return variance <= 0 ? 0 : variance.round();
  }

  Widget _buildActionMenu() {
  return GlassCard(
    padding: EdgeInsets.zero,
    child: Column(
      children: [
        _buildActionTile(
          icon: Icons.edit_rounded,
          color: RhythmaColors.primary,
          title: AppLocalizations.of(context)!.profileEditInfo,
          onTap: _showEditProfileSheet,
        ),
        Divider(height: 1, color: RhythmaColors.border),
        _buildActionTile(
          icon: Icons.emergency_rounded,
          color: RhythmaColors.rose,
          title: AppLocalizations.of(context)!.profileEmergencyContact,
          onTap: _showEmergencyContactsSheet,
        ),
        Divider(height: 1, color: RhythmaColors.border),
        _buildActionTile(
          icon: Icons.settings_rounded,
          color: RhythmaColors.foreground,
          title: AppLocalizations.of(context)!.profileAppSettings,
          onTap: () {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => const SettingsScreen(),
              ),
            ).then((_) {
              setState(() {
                _loadProfile();
              });
            });
          },
        ),
      ],
    ),
  );
}

  Widget _buildActionTile({
    required IconData icon,
    required Color color,
    required String title,
    required VoidCallback onTap,
  }) {
    return Semantics(
      button: true,
      label: title,
      child: ListTile(
        leading: TintedIcon(icon: icon, color: color, size: 36),
        title: Text(title, style: Theme.of(context).textTheme.bodyLarge),
        trailing: ExcludeSemantics(
          child: Icon(Icons.chevron_right_rounded, color: RhythmaColors.mutedFg),
        ),
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    context.watch<ThemeProvider>();
    final profile = context.watch<ProfileProvider>().profile;
    if (profile.isNotEmpty) {
      _userName = profile['name'] as String? ?? 'Aarya';
      _userAge = profile['age'] as int? ?? 28;
      _cycleLength = profile['cycle_length'] as int? ?? 28;
    }
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 240,
            pinned: true,
            backgroundColor: RhythmaColors.background,
            surfaceTintColor: Colors.transparent,
            flexibleSpace: FlexibleSpaceBar(
              background: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      RhythmaColors.primary.withValues(alpha: 0.15),
                      RhythmaColors.teal.withValues(alpha: 0.08),
                      RhythmaColors.background,
                    ],
                  ),
                ),
                child: SafeArea(
                  child: Column(
                    children: [
                      const SizedBox(height: 12),
                      _buildHeader(),
                    ],
                  ),
                ),
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
            sliver: SliverList(
              delegate: SliverChildListDelegate([
                _buildHealthSummary(),
                const SizedBox(height: 24),
                SectionHeader(title: AppLocalizations.of(context)!.profileQuickStats),
                _buildStatsCards(),
                const SizedBox(height: 24),
                SectionHeader(title: AppLocalizations.of(context)!.profileAccountSettings),
                _buildActionMenu(),
              ]),
            ),
          ),
        ],
      ),
    );
  }
  }
