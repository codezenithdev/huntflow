"""HuntFlow CLI for running job discovery, outreach, and interview prep."""
import click


@click.group()
def cli():
    """HuntFlow - AI-powered job hunting automation."""
    pass


@cli.command()
@click.option('--max-jobs', default=200, help='Maximum jobs to discover per run')
@click.option('--min-score', default=30, help='Minimum job score threshold')
def discover(max_jobs, min_score):
    """Run job discovery across all sources."""
    click.echo(f"Starting job discovery (max {max_jobs} jobs, min score {min_score})")


@cli.command()
@click.argument('job_id')
def apply(job_id):
    """Prepare application for a specific job."""
    click.echo(f"Preparing application for job {job_id}")


@cli.command()
@click.argument('job_id')
def interview(job_id):
    """Generate interview prep materials for a job."""
    click.echo(f"Generating interview prep for job {job_id}")


@cli.command()
def digest():
    """Generate and send daily digest."""
    click.echo("Generating daily digest and sending notifications")


@cli.command()
def dashboard():
    """Launch Streamlit dashboard."""
    import subprocess
    subprocess.run(['streamlit', 'run', 'dashboard/app.py'])


if __name__ == '__main__':
    cli()
