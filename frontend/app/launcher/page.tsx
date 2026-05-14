import Link from "next/link"
import { PageIntro } from "@/components/PageIntro"

const SERVER_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

const installSteps = [
  {
    title: "Установите Windows-приложение",
    body: "Используйте инсталлятор для стандартной установки или portable-версию, если нужен более легкий локальный вариант.",
  },
  {
    title: "Войдите через аккаунт лиги",
    body: "Авторизация в лаунчере привязывает локальный захват к той же учетной записи, что используется на сайте для кабинета и загрузок.",
  },
  {
    title: "Направьте телеметрию F1 25 на localhost",
    body: "Включите UDP-телеметрию и отправляйте ее на 127.0.0.1:20777, чтобы лаунчер мог захватывать сессии и публиковать результат в лигу.",
  },
]

const faqs = [
  {
    question: "Когда мне вообще нужен лаунчер?",
    answer: "Используйте его, когда нужен захват телеметрии, загрузка гонки или операторская загрузка со стороны хоста. Для просмотра сезонов, итогов гонок и профилей игроков десктопное приложение не требуется.",
  },
  {
    question: "Сайт полезен без него?",
    answer: "Да. Сайт остается опубликованным слоем для таблицы, итогов гонок, истории игроков и просмотра архива.",
  },
  {
    question: "Что проверить перед гоночным вечером?",
    answer: "Убедитесь, что вход работает, телеметрия направлена на 127.0.0.1:20777, а лаунчер видит игру еще до начала сессии.",
  },
]

export default function LauncherPage() {
  return (
    <div className="page-shell">
      <PageIntro
        eyebrow="Windows-лаунчер"
        title="Установите десктопный мост для захвата, загрузки и операторских действий со стороны хоста."
        description="Лаунчер это единственная часть продукта, которой нужна локальная установка. Он отвечает за захват телеметрии и авторизованную загрузку сессий, а сайт остается читаемым публичным слоем для сезона, архива гонок и профилей игроков."
        actions={
          <>
            <a href={`${SERVER_URL}/agent/installer`} className="ui-button-primary">
              Скачать установщик
            </a>
            <a href={`${SERVER_URL}/agent/download`} className="ui-button-secondary">
              Портативная версия
            </a>
          </>
        }
        meta={
          <>
            <span className="state-chip">Windows 10/11</span>
            <span className="data-pill">Вход через аккаунт лиги</span>
            <span className="data-pill">UDP-захват телеметрии</span>
          </>
        }
      />

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_360px]">
        <div className="surface-panel p-6 sm:p-8">
          <p className="eyebrow">Для чего нужен лаунчер</p>
          <h2 className="mt-3 section-title">Узкая десктопная роль, а не второй сайт.</h2>
          <p className="mt-4 max-w-[60ch] text-sm leading-7 text-muted">
            Модель должна быть простой: сайт это место, где читают лигу, а лаунчер это место, где данные гонки
            захватываются и передаются в систему лиги.
          </p>
          <div className="mt-6 definition-list">
            <div className="definition-row">
              <span className="mono-data text-text">Личное использование</span>
              <span className="text-muted">Захват практики, просмотр телеметрии и авторизованные загрузки с вашего компьютера.</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Для хоста</span>
              <span className="text-muted">Захват и загрузка со стороны лобби во время организованных гоночных вечеров.</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Результат на сайте</span>
              <span className="text-muted">Опубликованные таблицы, итоги гонок, профили игроков и история архива.</span>
            </div>
          </div>
        </div>

        <div className="surface-panel-muted p-6">
          <p className="eyebrow">Проверки перед стартом</p>
          <div className="mt-4 definition-list">
            <div className="definition-row">
              <span className="mono-data text-text">IP телеметрии</span>
              <span className="mono-data text-muted">127.0.0.1</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Порт телеметрии</span>
              <span className="mono-data text-muted">20777</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Рекомендуемая частота</span>
              <span className="mono-data text-muted">60 Гц</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Аккаунт</span>
              <span className="text-muted">Тот же аккаунт лиги, что и на сайте</span>
            </div>
          </div>
        </div>
      </section>

      <section className="list-panel">
        <div className="border-b border-border px-6 py-5">
          <p className="eyebrow">Установка</p>
          <h2 className="mt-2 section-title">Три шага от чистой машины до рабочего захвата.</h2>
        </div>
        {installSteps.map((step, index) => (
          <div key={step.title} className="list-row md:grid-cols-[80px_minmax(0,1fr)_220px] md:items-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-borderStrong bg-surfaceAlt font-display text-xl text-text">
              {index + 1}
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text">{step.title}</h3>
              <p className="mt-2 text-sm leading-7 text-muted">{step.body}</p>
            </div>
            <div className="text-sm text-muted md:text-right">
              {index === 0 ? "Установка" : index === 1 ? "Авторизация" : "Настройка телеметрии"}
            </div>
          </div>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="surface-panel p-6">
          <p className="eyebrow">Настройки игры</p>
          <h2 className="mt-3 section-title">Параметры телеметрии F1 25, которые нужно проверить перед первым запуском.</h2>
          <div className="mt-5 definition-list">
            <div className="definition-row">
              <span className="mono-data text-text">UDP-телеметрия</span>
              <span className="text-muted">Вкл.</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">UDP IP-адрес</span>
              <span className="mono-data text-muted">127.0.0.1</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">UDP-порт</span>
              <span className="mono-data text-muted">20777</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Частота отправки</span>
              <span className="mono-data text-muted">60 Гц</span>
            </div>
            <div className="definition-row">
              <span className="mono-data text-text">Формат</span>
              <span className="mono-data text-muted">2025</span>
            </div>
          </div>
        </div>

        <div className="surface-panel p-6">
          <p className="eyebrow">Частые вопросы перед установкой</p>
          <h2 className="mt-3 section-title">Короткие ответы на реальные блокеры.</h2>
          <div className="mt-5 space-y-3">
            {faqs.map((item) => (
              <div key={item.question} className="surface-panel-muted p-4">
                <h3 className="text-base font-semibold text-text">{item.question}</h3>
                <p className="mt-2 text-sm leading-7 text-muted">{item.answer}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="surface-panel p-6 sm:p-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="eyebrow">Следующий шаг</p>
            <h2 className="mt-3 section-title">Скачайте, войдите и вернитесь к текущему сезону.</h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <a href={`${SERVER_URL}/agent/installer`} className="ui-button-primary">
              Скачать установщик
            </a>
            <Link href="/login" className="ui-button-secondary">
              Войти
            </Link>
            <Link href="/seasons" className="ui-button-tertiary">
              Архив сезонов
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
