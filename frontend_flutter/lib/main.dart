import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'config/theme.dart';
import 'providers/auth_provider.dart';
import 'providers/integration_provider.dart';
import 'providers/invoice_provider.dart';
import 'providers/theme_provider.dart';
import 'screens/auth/accept_invite_screen.dart';
import 'screens/auth/login_screen.dart';
import 'screens/auth/signup_screen.dart';
import 'screens/landing/landing_screen.dart';
import 'widgets/app_shell.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SakshiFinanceApp());
}

class AppScrollBehavior extends MaterialScrollBehavior {
  @override
  Set<PointerDeviceKind> get dragDevices => {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.trackpad,
        PointerDeviceKind.stylus,
        PointerDeviceKind.unknown,
      };
}

class SakshiFinanceApp extends StatelessWidget {
  const SakshiFinanceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => InvoiceProvider()),
        ChangeNotifierProvider(create: (_) => IntegrationProvider()),
      ],
      child: Consumer2<ThemeProvider, AuthProvider>(
        builder: (context, themeProv, authProv, _) {
          return MaterialApp(
            title: 'Sakshi Finance - Automated Accounting & Tax Engine',
            debugShowCheckedModeBanner: false,
            scrollBehavior: AppScrollBehavior(),
            themeMode: themeProv.themeMode,
            theme: AppTheme.lightTheme,
            darkTheme: AppTheme.darkTheme,
            builder: (context, child) {
              return AnimatedTheme(
                data: themeProv.isDarkMode ? AppTheme.darkTheme : AppTheme.lightTheme,
                duration: const Duration(milliseconds: 350),
                curve: Curves.easeInOut,
                child: child ?? const SizedBox.shrink(),
              );
            },
            onGenerateRoute: (settings) {
              final uri = Uri.tryParse(settings.name ?? '');
              if (uri != null && uri.path == '/accept-invite') {
                final token = uri.queryParameters['token'] ?? '';
                return MaterialPageRoute(
                  builder: (_) => AcceptInviteScreen(token: token),
                  settings: settings,
                );
              }
              if (settings.name == '/login') {
                return MaterialPageRoute(
                  builder: (_) => const LoginScreen(),
                  settings: settings,
                );
              }
              if (settings.name == '/signup') {
                return MaterialPageRoute(
                  builder: (_) => const SignUpScreen(),
                  settings: settings,
                );
              }
              return MaterialPageRoute(
                builder: (_) => authProv.isAuthenticated ? const AppShell() : const LandingScreen(),
                settings: settings,
              );
            },
            home: authProv.isAuthenticated ? const AppShell() : const LandingScreen(),
          );
        },
      ),
    );
  }
}
