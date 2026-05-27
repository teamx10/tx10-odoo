# Task: TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта

<!-- tx2-task
id: 2026-05-26-ai-document-foldering
title: TeamX10 AI — Auto-foldering: загрузка и автоклассификация документов проекта
goal: Пользователь загружает файлы в проект → детерминированный классификатор (Subbotik24 keyword rules) определяет тип и кладёт файл в правильную папку дерева проекта (TEO_Solar-структура); нераспознанное → папка «Нераспознанное» + needs_review.
size: M
status: iterating
created: 2026-05-26
design: .pm/tasks/2026-05-26-ai-document-foldering/design.md
-->

## Goal

Пользователь загружает файлы в проект → детерминированный классификатор (Subbotik24 keyword rules) определяет тип и кладёт файл в правильную папку дерева проекта (TEO_Solar-структура); нераспознанное → папка «Нераспознанное» + needs_review.

## Design Reference

See `design.md` (copied into this task directory) for full design and locked decisions.

## Status

- [x] spec-task complete
- [x] flow-task complete
- [x] PR created: https://github.com/teamx10/tx10-odoo/pull/4
