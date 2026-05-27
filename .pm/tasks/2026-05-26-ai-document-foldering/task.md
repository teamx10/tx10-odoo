# Task: TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта

<!-- tx2-task
id: 2026-05-26-ai-document-foldering
title: TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта
goal: Пользователь загружает файлы в проект → детерминированный классификатор (Subbotik24 keyword rules) определяет тип и кладёт файл в правильную папку дерева проекта (TEO_Solar-структура); нераспознанное → папка «Нераспознанное» + needs_review.
size: M
status: review-pending
created: 2026-05-26
design: .pm/tasks/2026-05-26-ai-document-foldering/design.md
-->

## Goal

Пользователь загружает файлы в проект → детерминированный классификатор (Subbotik24 keyword rules) определяет тип и кладёт файл в правильную папку дерева проекта (TEO_Solar-структура); нераспознанное → папка «Нераспознанное» + needs_review.

## Design Reference

See `design.md` (copied into this task directory) for full design and locked decisions.

## Status

- [x] spec-task complete
- [x] flow-task complete (iteration 2 — LLM pivot)
- [x] consensus gate PASS (0/0/0 after 2 repair iterations)
- [x] 93 backend tests pass against live `isolar` DB
- [x] live UI smoke verified (smart buttons, wizard, grouped docs list)
- [x] PR updated: https://github.com/teamx10/tx10-odoo/pull/4
- [ ] human review / `/tx2:complete` to finalize
