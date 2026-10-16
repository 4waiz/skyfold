using System;

namespace Skyfold
{
    /// <summary>Tiny message hub so gameplay code can surface text without knowing about UI.</summary>
    public static class HUDMessages
    {
        public static event Action<string, bool> ToastRequested;   // text, warning
        public static event Action<string> HintChanged;            // contextual line (null clears)
        public static event Action<string> CursorHintChanged;      // desktop plinth hover text

        public static string Hint { get; private set; }
        public static string CursorHint { get; private set; }

        public static void Toast(string text, bool warning = false)
        {
            if (string.IsNullOrEmpty(text)) return;
            ToastRequested?.Invoke(text, warning);
        }

        public static void SetHint(string text)
        {
            if (text == Hint) return;
            Hint = text;
            HintChanged?.Invoke(text);
        }

        public static void SetCursorHint(string text)
        {
            if (text == CursorHint) return;
            CursorHint = text;
            CursorHintChanged?.Invoke(text);
        }
    }
}
