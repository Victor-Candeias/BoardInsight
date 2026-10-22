using System;
using System.Collections.Generic;

namespace BoardInsight.Desktop
{
    /// <summary>
    /// Endereço do BoardInsight e opções da app. Sem dependências de WPF para poder ser testado em qualquer SO.
    /// Prioridade do URL: argumento <c>--url</c> &gt; variável BOARDINSIGHT_URL &gt; registo (instalador) &gt; omissão.
    /// </summary>
    public sealed class DesktopSettings
    {
        public const string DefaultUrl = "http://localhost:8080/";
        public const string UrlEnvironmentVariable = "BOARDINSIGHT_URL";

        private DesktopSettings(Uri baseUrl, bool devTools)
        {
            BaseUrl = baseUrl;
            DevTools = devTools;
        }

        /// <summary>Origem da SPA, sempre na forma <c>esquema://anfitrião:porta/</c>.</summary>
        public Uri BaseUrl { get; }

        public bool DevTools { get; }

        public Uri HealthUrl => new Uri(BaseUrl, "health");

        public static DesktopSettings Resolve(IReadOnlyList<string> args, string? environmentUrl, string? registryUrl)
        {
            string? argumentUrl = null;
            var devTools = false;
            for (var i = 0; i < args.Count; i++)
            {
                var arg = args[i];
                if (string.Equals(arg, "--devtools", StringComparison.OrdinalIgnoreCase))
                    devTools = true;
                else if (arg.StartsWith("--url=", StringComparison.OrdinalIgnoreCase))
                    argumentUrl = arg.Substring("--url=".Length);
                else if (string.Equals(arg, "--url", StringComparison.OrdinalIgnoreCase) && i + 1 < args.Count)
                    argumentUrl = args[++i];
            }

            var baseUrl = TryNormalize(argumentUrl) ?? TryNormalize(environmentUrl) ?? TryNormalize(registryUrl)
                ?? new Uri(DefaultUrl);
            return new DesktopSettings(baseUrl, devTools);
        }

        /// <summary>Aceita só URLs http/https absolutos; devolve a origem (o caminho é ignorado: a SPA está na raiz).</summary>
        public static Uri? TryNormalize(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return null;
            if (!Uri.TryCreate(value!.Trim(), UriKind.Absolute, out var uri))
                return null;
            if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps)
                return null;
            return new Uri(uri.GetLeftPart(UriPartial.Authority) + "/");
        }

        /// <summary>True se o endereço pertence ao BoardInsight (mesma origem) e deve abrir dentro da app.</summary>
        public bool IsAppUri(string? value)
        {
            if (string.IsNullOrEmpty(value) || !Uri.TryCreate(value, UriKind.Absolute, out var uri))
                return false;
            return Uri.Compare(uri, BaseUrl, UriComponents.SchemeAndServer, UriFormat.Unescaped,
                StringComparison.OrdinalIgnoreCase) == 0;
        }

        /// <summary>Endereços externos que podem ser entregues ao browser predefinido (nunca file:, javascript:, etc.).</summary>
        public static bool CanOpenExternally(string? value)
        {
            if (string.IsNullOrEmpty(value) || !Uri.TryCreate(value, UriKind.Absolute, out var uri))
                return false;
            return uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps || uri.Scheme == Uri.UriSchemeMailto;
        }
    }
}
