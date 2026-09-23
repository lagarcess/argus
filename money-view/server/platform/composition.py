"""Compose local domains and their explicit data-lifecycle callbacks."""

from fastapi import FastAPI

from ..store import Store
from . import (
    assistant,
    chat,
    commands,
    deposits,
    identity,
    investing,
    ledger,
    omnisearch,
    planning,
    runtime,
    services,
)
from .guest_demo import seed_guest_ledger

DOMAINS = (ledger, investing, planning, services, assistant)


def mount(application: FastAPI) -> None:
    application.include_router(identity.router)
    application.include_router(runtime.router)
    for domain in DOMAINS:
        application.include_router(domain.router)
    application.include_router(chat.router)
    application.include_router(omnisearch.router)


def initialize(application: FastAPI, store: Store) -> None:
    application.state.store = store
    runtime.initialize(store)
    sessions = identity.Identity(store)
    sessions.initialize()
    application.state.identity = sessions
    for domain in DOMAINS:
        domain.initialize(store)
    commands.initialize(store)
    chat.initialize(store)
    omnisearch.initialize(store)
    sessions.register_guest_seed(seed_guest_ledger)
    # Clear dependent records before ledger accounts; the callbacks share a transaction.
    for domain in (commands, chat, runtime, assistant, services, planning, investing, ledger, deposits):
        sessions.register_data_domain(
            domain.__name__.rsplit(".", 1)[1],
            export=domain.export_data,
            clear=domain.clear_data,
            usage=domain.usage_data,
        )
