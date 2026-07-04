import { Component, type ReactNode } from "react";
import i18n from "../i18n";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      const t = (key: string) => i18n.t(key);
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#0a0a0a] px-4">
          <div className="max-w-sm w-full rounded-2xl border border-[#2a2a2a] bg-[#141414] p-8 text-center">
            <p className="text-base font-semibold text-[#ddd] mb-2">
              {t("errorBoundary.heading")}
            </p>
            <p className="text-sm text-[#888] mb-6">
              {t("errorBoundary.body")}
            </p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-lg px-4 py-2 text-sm font-semibold bg-[#1db954] text-black hover:bg-[#1ed760] transition-colors"
            >
              {t("errorBoundary.reload")}
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
