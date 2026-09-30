import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../config/theme.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../screens/admin/admin_users_screen.dart';
import '../screens/dashboard/dashboard_screen.dart';
import '../screens/inbox/email_inbox_screen.dart';
import '../screens/integrations/integrations_screen.dart';
import '../screens/invoices/invoice_list_screen.dart';
import '../screens/settings/settings_screen.dart';
import '../screens/upload/upload_screen.dart';
import 'aurora_background.dart';
import 'change_password_dialog.dart';
import 'network_status_banner.dart';
import 'system_status_dialog.dart';

class AppShell extends StatefulWidget {
  final int initialIndex;

  const AppShell({super.key, this.initialIndex = 0});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _ShellNavItem {
  final String title;
  final String shortTitle;
  final IconData icon;
  final IconData activeIcon;
  final Widget screen;
  final bool adminOnly;

  const _ShellNavItem({
    required this.title,
    required this.shortTitle,
    required this.icon,
    required this.activeIcon,
    required this.screen,
    this.adminOnly = false,
  });
}

class _AppShellState extends State<AppShell> {
  late int _currentIndex;
  bool _isSidebarCollapsed = false;
  bool _hasPromptedPasswordChange = false;

  static const List<_ShellNavItem> _allNavItems = [
    _ShellNavItem(
      title: 'Dashboard',
      shortTitle: 'Home',
      icon: Icons.grid_view_rounded,
      activeIcon: Icons.grid_view_rounded,
      screen: DashboardScreen(),
    ),
    _ShellNavItem(
      title: 'Upload & OCR',
      shortTitle: 'Upload',
      icon: Icons.cloud_upload_outlined,
      activeIcon: Icons.cloud_upload_rounded,
      screen: UploadScreen(),
    ),
    _ShellNavItem(
      title: 'Invoices & Bills',
      shortTitle: 'Invoices',
      icon: Icons.receipt_long_outlined,
      activeIcon: Icons.receipt_long_rounded,
      screen: InvoiceListScreen(),
    ),
    _ShellNavItem(
      title: 'Email Inbox',
      shortTitle: 'Inbox',
      icon: Icons.mark_email_unread_outlined,
      activeIcon: Icons.mark_email_unread_rounded,
      screen: EmailInboxScreen(),
    ),
    _ShellNavItem(
      title: 'Zoho & Integrations',
      shortTitle: 'Zoho',
      icon: Icons.hub_outlined,
      activeIcon: Icons.hub_rounded,
      screen: IntegrationsScreen(),
    ),
    _ShellNavItem(
      title: 'Administration',
      shortTitle: 'Admin',
      icon: Icons.admin_panel_settings_outlined,
      activeIcon: Icons.admin_panel_settings_rounded,
      screen: AdminUsersScreen(),
      adminOnly: true,
    ),
    _ShellNavItem(
      title: 'Settings',
      shortTitle: 'Settings',
      icon: Icons.tune_rounded,
      activeIcon: Icons.tune_rounded,
      screen: SettingsScreen(),
    ),
  ];

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkMustChangePassword();
    });
  }

  void _checkMustChangePassword() {
    if (_hasPromptedPasswordChange) return;
    final auth = Provider.of<AuthProvider>(context, listen: false);
    if (auth.currentUser?.mustChangePassword == true) {
      _hasPromptedPasswordChange = true;
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (_) => const ChangePasswordDialog(isForced: true),
      );
    }
  }

  void _onSelectTab(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  void _toggleSidebar() {
    setState(() {
      _isSidebarCollapsed = !_isSidebarCollapsed;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final size = MediaQuery.of(context).size;
    final isDesktop = size.width >= 850;

    final authProvider = Provider.of<AuthProvider>(context);
    final themeProvider = Provider.of<ThemeProvider>(context);
    final bool isAdmin = authProvider.isAdmin;

    final visibleNavItems = _allNavItems.where((item) => !item.adminOnly || isAdmin).toList();
    final activeIndex = (_currentIndex >= visibleNavItems.length) ? 0 : _currentIndex;

    if (isDesktop) {
      final sidebarWidth = _isSidebarCollapsed ? 80.0 : 260.0;

      return Scaffold(
        body: NetworkStatusBanner(
          child: AuroraBackground(
            child: Row(
            children: [
              // Premium Clean Silky-Smooth Collapsible Sidebar Navigation
              AnimatedContainer(
                duration: const Duration(milliseconds: 300),
                curve: Curves.fastOutSlowIn,
                width: sidebarWidth,
                decoration: BoxDecoration(
                  color: isDark ? const Color(0xFF0F172A) : Colors.white,
                  border: Border(
                    right: BorderSide(
                      color: isDark ? AppTheme.darkBorder : AppTheme.lightBorder,
                      width: 1,
                    ),
                  ),
                ),
                child: ClipRect(
                  child: OverflowBox(
                    minWidth: 260,
                    maxWidth: 260,
                    alignment: Alignment.topLeft,
                    child: SizedBox(
                      width: 260,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // App Brand Header with Smooth Transition & Persistent Company Symbol
                          SizedBox(
                            height: 68,
                            child: Row(
                              children: [
                                // Company Symbol Badge (Always visible & stationary)
                                SizedBox(
                                  width: 80,
                                  child: Center(
                                    child: Tooltip(
                                      message: _isSidebarCollapsed ? 'Sakshi Finance (Click to expand)' : 'Sakshi Finance',
                                      child: InkWell(
                                        onTap: _isSidebarCollapsed ? _toggleSidebar : null,
                                        borderRadius: BorderRadius.circular(11),
                                        child: Container(
                                          width: 40,
                                          height: 40,
                                          decoration: BoxDecoration(
                                            gradient: AppTheme.primaryGradient,
                                            borderRadius: BorderRadius.circular(11),
                                            boxShadow: [
                                              BoxShadow(
                                                color: AppTheme.primaryColor.withValues(alpha: 0.35),
                                                blurRadius: 8,
                                                offset: const Offset(0, 2),
                                              ),
                                            ],
                                          ),
                                          child: const Center(
                                            child: Icon(Icons.account_balance_wallet_rounded, color: Colors.white, size: 20),
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                                // Smoothly Fading Brand Name & Collapse Action
                                Expanded(
                                  child: AnimatedOpacity(
                                    duration: const Duration(milliseconds: 200),
                                    curve: Curves.easeInOut,
                                    opacity: _isSidebarCollapsed ? 0.0 : 1.0,
                                    child: Padding(
                                      padding: const EdgeInsets.only(right: 8),
                                      child: Row(
                                        children: [
                                          Expanded(
                                            child: Column(
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              mainAxisAlignment: MainAxisAlignment.center,
                                              children: [
                                                Text(
                                                  'Sakshi Finance',
                                                  maxLines: 1,
                                                  softWrap: false,
                                                  overflow: TextOverflow.clip,
                                                  style: TextStyle(
                                                    fontSize: 15.5,
                                                    fontWeight: FontWeight.w800,
                                                    letterSpacing: -0.3,
                                                    color: isDark ? Colors.white : const Color(0xFF0F172A),
                                                  ),
                                                ),
                                                const SizedBox(height: 1),
                                                Text(
                                                  'Autonomous AP AI',
                                                  maxLines: 1,
                                                  softWrap: false,
                                                  overflow: TextOverflow.clip,
                                                  style: TextStyle(
                                                    fontSize: 11,
                                                    fontWeight: FontWeight.w600,
                                                    color: isDark ? AppTheme.secondaryColor : AppTheme.primaryColor,
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                          Tooltip(
                                            message: 'Collapse Menu',
                                            child: IconButton(
                                              icon: const Icon(Icons.chevron_left_rounded, size: 22),
                                              onPressed: _isSidebarCollapsed ? null : _toggleSidebar,
                                              color: isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B),
                                              visualDensity: VisualDensity.compact,
                                              padding: const EdgeInsets.all(4),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          Divider(height: 1, color: isDark ? AppTheme.darkBorder : AppTheme.lightBorder),

                          // Nav Items with Smooth Fade and Zero Shift
                          Expanded(
                            child: ListView.builder(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                              itemCount: visibleNavItems.length,
                              itemBuilder: (context, index) {
                                final item = visibleNavItems[index];
                                final isSelected = activeIndex == index;

                                return Container(
                                  margin: const EdgeInsets.only(bottom: 4),
                                  child: Tooltip(
                                    message: _isSidebarCollapsed ? item.title : '',
                                    preferBelow: false,
                                    child: Material(
                                      color: Colors.transparent,
                                      child: InkWell(
                                        onTap: () => _onSelectTab(index),
                                        borderRadius: BorderRadius.circular(10),
                                        child: AnimatedContainer(
                                          duration: const Duration(milliseconds: 200),
                                          height: 42,
                                          padding: const EdgeInsets.symmetric(horizontal: 4),
                                          decoration: BoxDecoration(
                                            color: isSelected
                                                ? AppTheme.primaryColor.withValues(alpha: isDark ? 0.18 : 0.08)
                                                : Colors.transparent,
                                            borderRadius: BorderRadius.circular(10),
                                            border: isSelected
                                                ? Border.all(color: AppTheme.primaryColor.withValues(alpha: 0.25), width: 1)
                                                : null,
                                          ),
                                          child: Row(
                                            children: [
                                              SizedBox(
                                                width: 52,
                                                child: Center(
                                                  child: Icon(
                                                    isSelected ? item.activeIcon : item.icon,
                                                    color: isSelected
                                                        ? AppTheme.primaryColor
                                                        : (isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B)),
                                                    size: 20,
                                                  ),
                                                ),
                                              ),
                                              Expanded(
                                                child: AnimatedOpacity(
                                                  duration: const Duration(milliseconds: 200),
                                                  curve: Curves.easeInOut,
                                                  opacity: _isSidebarCollapsed ? 0.0 : 1.0,
                                                  child: Padding(
                                                    padding: const EdgeInsets.only(left: 4, right: 6),
                                                    child: Text(
                                                      item.title,
                                                      maxLines: 1,
                                                      softWrap: false,
                                                      overflow: TextOverflow.clip,
                                                      style: TextStyle(
                                                        color: isSelected
                                                            ? (isDark ? Colors.white : AppTheme.primaryColor)
                                                            : (isDark ? AppTheme.darkTextPrimary : const Color(0xFF334155)),
                                                        fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                                                        fontSize: 13,
                                                        letterSpacing: -0.1,
                                                      ),
                                                    ),
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                          Divider(height: 1, color: isDark ? AppTheme.darkBorder : AppTheme.lightBorder),

                          // User Footer with Seamless AnimatedCrossFade
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
                            child: AnimatedCrossFade(
                              duration: const Duration(milliseconds: 280),
                              firstCurve: Curves.easeInOutCubic,
                              secondCurve: Curves.easeInOutCubic,
                              sizeCurve: Curves.easeInOutCubic,
                              crossFadeState: _isSidebarCollapsed
                                  ? CrossFadeState.showSecond
                                  : CrossFadeState.showFirst,
                              firstChild: Row(
                                children: [
                                  Container(
                                    width: 34,
                                    height: 34,
                                    margin: const EdgeInsets.symmetric(horizontal: 14),
                                    decoration: BoxDecoration(
                                      gradient: AppTheme.primaryGradient,
                                      shape: BoxShape.circle,
                                      boxShadow: [
                                        BoxShadow(
                                          color: AppTheme.primaryColor.withValues(alpha: 0.3),
                                          blurRadius: 6,
                                        ),
                                      ],
                                    ),
                                    child: Center(
                                      child: Text(
                                        (authProvider.currentUser?.fullName ?? authProvider.currentUser?.email ?? 'U')[0].toUpperCase(),
                                        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13),
                                      ),
                                    ),
                                  ),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      mainAxisSize: MainAxisSize.min,
                                      children: [
                                        Text(
                                          authProvider.currentUser?.fullName ?? 'Finance User',
                                          maxLines: 1,
                                          softWrap: false,
                                          overflow: TextOverflow.clip,
                                          style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
                                        ),
                                        Text(
                                          authProvider.currentUser?.email ?? '',
                                          maxLines: 1,
                                          softWrap: false,
                                          overflow: TextOverflow.clip,
                                          style: TextStyle(
                                            fontSize: 10.5,
                                            color: isDark ? AppTheme.darkTextMuted : AppTheme.lightTextMuted,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  _buildSystemHealthButton(isDark),
                                  const SizedBox(width: 4),
                                  _buildThemeSymbolButton(themeProvider, isDark),
                                  const SizedBox(width: 2),
                                  IconButton(
                                    icon: const Icon(Icons.logout_rounded, size: 18),
                                    onPressed: () => authProvider.logout(),
                                    tooltip: 'Sign Out',
                                    visualDensity: VisualDensity.compact,
                                    padding: const EdgeInsets.all(6),
                                    constraints: const BoxConstraints(),
                                  ),
                                ],
                              ),
                              secondChild: SizedBox(
                                width: 80,
                                child: Column(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Tooltip(
                                      message: authProvider.currentUser?.fullName ?? authProvider.currentUser?.email ?? 'User',
                                      child: Container(
                                        width: 34,
                                        height: 34,
                                        decoration: BoxDecoration(
                                          gradient: AppTheme.primaryGradient,
                                          shape: BoxShape.circle,
                                        ),
                                        child: Center(
                                          child: Text(
                                            (authProvider.currentUser?.fullName ?? authProvider.currentUser?.email ?? 'U')[0].toUpperCase(),
                                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 13),
                                          ),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(height: 10),
                                    _buildSystemHealthButton(isDark),
                                    const SizedBox(height: 6),
                                    _buildThemeSymbolButton(themeProvider, isDark),
                                    const SizedBox(height: 6),
                                    IconButton(
                                      icon: const Icon(Icons.logout_rounded, size: 18),
                                      onPressed: () => authProvider.logout(),
                                      tooltip: 'Sign Out',
                                      visualDensity: VisualDensity.compact,
                                      padding: const EdgeInsets.all(6),
                                      constraints: const BoxConstraints(),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              // Main Screen Body
              Expanded(
                child: IndexedStack(
                  index: activeIndex,
                  children: visibleNavItems.map((e) => e.screen).toList(),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

    // Mobile / Narrow Layout
    return Scaffold(
      appBar: AppBar(
        title: Text(visibleNavItems[activeIndex].title),
        actions: [
          _buildSystemHealthButton(isDark),
          Padding(
            padding: const EdgeInsets.only(right: 8, left: 4),
            child: _buildThemeSymbolButton(themeProvider, isDark),
          ),
          IconButton(
            icon: const Icon(Icons.logout_rounded),
            onPressed: () => authProvider.logout(),
          ),
        ],
      ),
      body: NetworkStatusBanner(
        child: AuroraBackground(
          child: IndexedStack(
            index: activeIndex,
            children: visibleNavItems.map((e) => e.screen).toList(),
          ),
        ),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: isDark ? const Color(0xFF0F172A) : Colors.white,
          border: Border(
            top: BorderSide(
              color: isDark ? AppTheme.darkBorder : AppTheme.lightBorder,
              width: 1,
            ),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: isDark ? 0.3 : 0.05),
              blurRadius: 10,
              offset: const Offset(0, -2),
            ),
          ],
        ),
        child: SafeArea(
          child: SizedBox(
            height: 60,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: List.generate(visibleNavItems.length, (index) {
                final item = visibleNavItems[index];
                final isSelected = activeIndex == index;
                final label = item.shortTitle;

                return Expanded(
                  child: InkWell(
                    onTap: () => _onSelectTab(index),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? AppTheme.primaryColor.withValues(alpha: isDark ? 0.22 : 0.12)
                                : Colors.transparent,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(
                            isSelected ? item.activeIcon : item.icon,
                            color: isSelected
                                ? AppTheme.primaryColor
                                : (isDark ? AppTheme.darkTextSecondary : const Color(0xFF64748B)),
                            size: 20,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: isSelected ? FontWeight.w700 : FontWeight.w500,
                            color: isSelected
                                ? (isDark ? Colors.white : AppTheme.primaryColor)
                                : (isDark ? AppTheme.darkTextMuted : const Color(0xFF64748B)),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSystemHealthButton(bool isDark) {
    return Tooltip(
      message: 'System Health & Diagnostics',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            showDialog(
              context: context,
              builder: (context) => const SystemStatusDialog(),
            );
          },
          borderRadius: BorderRadius.circular(9),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            padding: const EdgeInsets.all(7),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(9),
              border: Border.all(
                color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
              ),
            ),
            child: const Icon(
              Icons.monitor_heart_outlined,
              size: 17,
              color: Color(0xFF10B981),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildThemeSymbolButton(ThemeProvider themeProvider, bool isDark) {
    return Tooltip(
      message: isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => themeProvider.toggleTheme(),
          borderRadius: BorderRadius.circular(9),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeInOut,
            padding: const EdgeInsets.all(7),
            decoration: BoxDecoration(
              color: isDark ? const Color(0xFF1E293B) : const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(9),
              border: Border.all(
                color: isDark ? const Color(0xFF334155) : const Color(0xFFCBD5E1),
              ),
            ),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 300),
              transitionBuilder: (child, anim) => RotationTransition(
                turns: Tween<double>(begin: 0.75, end: 1.0).animate(anim),
                child: FadeTransition(opacity: anim, child: child),
              ),
              child: Icon(
                isDark ? Icons.light_mode_rounded : Icons.dark_mode_rounded,
                key: ValueKey(isDark),
                size: 17,
                color: isDark ? const Color(0xFFFBBF24) : const Color(0xFF6366F1),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

