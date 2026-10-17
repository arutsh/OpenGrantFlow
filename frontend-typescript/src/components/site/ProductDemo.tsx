export function ProductDemo() {
  return (
    <section id="demo" className="max-w-4xl mx-auto px-6 py-16">
      <div className="text-center mb-10">
        <p className="text-xs font-semibold tracking-widest uppercase mb-3 text-brand-gold">
          See It In Action
        </p>
        <h2 className="text-3xl font-bold text-brand-slate">
          Watch a 30 seconds product tour
        </h2>
      </div>
      <div className="relative w-full aspect-video rounded-xl shadow-2xl border border-slate-200 overflow-hidden">
        <iframe
          src="https://demo.arcade.software/video/bJX6Bh5bfgTZU5E2pUSK?embed&embed_mobile=inline&embed_desktop=inline&show_copy_link=true"
          title="OpenGrantFlow - Grant Management Without Spreadsheets"
          loading="lazy"
          allow="clipboard-write; autoplay"
          allowFullScreen
          className="absolute inset-0 h-full w-full"
        />
      </div>
    </section>
  );
}
