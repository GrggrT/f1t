// Roadmap PR 1.2.5 — full season management UI is deferred to Sprint 4.
// The earlier implementation hit several endpoints that no longer exist
// (or never existed) and would 404 in production; replace with a
// transparent stub so users see a useful message instead of a broken page.

export default function SeasonManageStubPage() {
  return (
    <main className="container mx-auto px-4 py-12">
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-8 text-center">
        <h1 className="text-2xl font-semibold text-amber-900">
          Управление сезоном недоступно
        </h1>
        <p className="mt-4 text-amber-700">
          Эта страница временно отключена и будет переработана в ближайшем обновлении.
          Если вам нужно изменить календарь или настройки сезона, обратитесь к администратору.
        </p>
      </div>
    </main>
  );
}
