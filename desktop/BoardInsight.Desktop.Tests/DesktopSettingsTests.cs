using System;
using BoardInsight.Desktop;
using Xunit;

namespace BoardInsight.Desktop.Tests
{
    public class DesktopSettingsTests
    {
        [Fact]
        public void UsaOmissaoSemConfiguracao()
        {
            var settings = DesktopSettings.Resolve(Array.Empty<string>(), null, null);

            Assert.Equal(new Uri("http://localhost:8080/"), settings.BaseUrl);
            Assert.Equal(new Uri("http://localhost:8080/health"), settings.HealthUrl);
            Assert.False(settings.DevTools);
        }

        [Fact]
        public void ArgumentoPrevaleceSobreVariavelERegisto()
        {
            var settings = DesktopSettings.Resolve(
                new[] { "--url", "http://10.0.0.5:9000/qualquer/caminho", "--devtools" },
                "http://localhost:7000/",
                "http://localhost:8081/");

            Assert.Equal(new Uri("http://10.0.0.5:9000/"), settings.BaseUrl);
            Assert.True(settings.DevTools);
        }

        [Fact]
        public void ValoresInvalidosPassamAoSeguinte()
        {
            var settings = DesktopSettings.Resolve(new[] { "--url=file:///C:/Windows" }, "não é um url", "http://localhost:8081");

            Assert.Equal(new Uri("http://localhost:8081/"), settings.BaseUrl);
        }

        [Theory]
        [InlineData("http://localhost:8080/cards?open=true", true)]
        [InlineData("HTTP://LOCALHOST:8080/", true)]
        [InlineData("http://localhost:8081/", false)]
        [InlineData("https://localhost:8080/", false)]
        [InlineData("https://cttv8.kanbanize.com/ctrl_board/96", false)]
        [InlineData("not a uri", false)]
        public void SoAMesmaOrigemAbreDentroDaApp(string uri, bool expected)
        {
            var settings = DesktopSettings.Resolve(Array.Empty<string>(), null, "http://localhost:8080/");

            Assert.Equal(expected, settings.IsAppUri(uri));
        }

        [Theory]
        [InlineData("https://cttv8.kanbanize.com/ctrl_board/96", true)]
        [InlineData("mailto:equipa@example.com", true)]
        [InlineData("file:///C:/Windows/System32/cmd.exe", false)]
        [InlineData("javascript:alert(1)", false)]
        [InlineData(null, false)]
        public void SoEsquemasSegurosVaoParaOBrowser(string? uri, bool expected)
        {
            Assert.Equal(expected, DesktopSettings.CanOpenExternally(uri));
        }
    }
}
