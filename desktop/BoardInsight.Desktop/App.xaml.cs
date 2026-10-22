using System;
using System.Threading;
using System.Windows;
using System.Windows.Threading;
using Microsoft.Win32;

namespace BoardInsight.Desktop
{
    public partial class App : Application
    {
        /// <summary>Nome partilhado com o AppMutex do instalador (boardinsight.iss): pede para fechar a app antes de atualizar.</summary>
        private const string MutexName = "BoardInsight.Desktop";
        private const string RegistryKeyPath = @"SOFTWARE\BoardInsight";

        private Mutex? _mutex;

        protected override void OnStartup(StartupEventArgs e)
        {
            base.OnStartup(e);
            _mutex = new Mutex(false, MutexName);
            DispatcherUnhandledException += OnUnhandledException;

            var settings = DesktopSettings.Resolve(
                e.Args,
                Environment.GetEnvironmentVariable(DesktopSettings.UrlEnvironmentVariable),
                ReadRegistryUrl());
            MainWindow = new MainWindow(settings);
            MainWindow.Show();
        }

        protected override void OnExit(ExitEventArgs e)
        {
            _mutex?.Dispose();
            base.OnExit(e);
        }

        /// <summary>URL gravado pelo instalador em HKLM\SOFTWARE\BoardInsight (valor Url), com a porta escolhida.</summary>
        private static string? ReadRegistryUrl()
        {
            try
            {
                using var root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, RegistryView.Registry64);
                using var key = root.OpenSubKey(RegistryKeyPath);
                return key?.GetValue("Url") as string;
            }
            catch (Exception)
            {
                return null;
            }
        }

        private static void OnUnhandledException(object sender, DispatcherUnhandledExceptionEventArgs e)
        {
            MessageBox.Show("Ocorreu um erro inesperado no BoardInsight:\n\n" + e.Exception.Message,
                "BoardInsight", MessageBoxButton.OK, MessageBoxImage.Error);
            e.Handled = true;
        }
    }
}
