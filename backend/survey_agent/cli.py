"""Operational CLI commands (``flask --app wsgi <command>``)."""
from __future__ import annotations

import click
from flask import Flask
from sqlalchemy import select

from .extensions import db
from .models import User
from .schemas import QuestionIn, SurveySettings


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    @click.option("--email", default="demo@surveyagent.dev")
    @click.option("--password", default="demo-password")
    @click.option("--plan", default="team", type=click.Choice(["free", "pro", "team", "enterprise"]))
    def seed_demo(email: str, password: str, plan: str) -> None:
        """Create a demo account with a published sample survey."""
        from .services.accounts import create_organization
        from .services.surveys import create_survey, publish

        if db.session.scalar(select(User).where(User.email == email)):
            click.echo(f"{email} already exists, skipping")
            return
        user = User(email=email, name="Demo User")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        org = create_organization("Acme Research", owner=user)
        org.subscription.plan = plan
        survey = create_survey(
            org,
            title="Customer Experience Pulse",
            description="A three-minute check-in on how we're doing.",
            settings=SurveySettings(modes=["form", "chat", "voice"], welcome_message="Hi! Thanks for helping us improve."),
            questions=[
                QuestionIn(type="nps", title="How likely are you to recommend Acme to a friend or colleague?", required=True),
                QuestionIn(
                    type="single_choice",
                    title="How long have you been a customer?",
                    options={"choices": ["Less than 6 months", "6-12 months", "1-3 years", "More than 3 years"]},
                    required=True,
                ),
                QuestionIn(
                    type="multiple_choice",
                    title="Which features do you use most?",
                    options={"choices": ["Dashboards", "Reports", "Integrations", "Mobile app"]},
                ),
                QuestionIn(type="rating", title="How satisfied are you with our support team?",
                           options={"min": 1, "max": 5, "min_label": "Very unsatisfied", "max_label": "Very satisfied"}),
                QuestionIn(type="long_text", title="What's one thing we could do better?"),
            ],
            created_by_id=user.id,
        )
        publish(survey, org)
        click.echo(f"Seeded {email} / {password} (plan: {plan}); survey token: {survey.public_token}")
