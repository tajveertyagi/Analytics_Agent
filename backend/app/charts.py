"""Plotly figure builders. Each function takes the DataFrame shape produced
by the matching src.analytics function and returns a go.Figure, reused by
both the Dashboard pages and the chatbot's chart-rendering.
"""
import plotly.express as px
import plotly.graph_objects as go


def fig_loss_trend(df, group_by=None):
    color = group_by if group_by and group_by in df.columns else None
    fig = px.line(
        df, x="Date", y="Distribution_Loss_Pct", color=color,
        markers=True, title="Distribution Loss % Over Time",
    )
    fig.update_layout(yaxis_title="Avg Loss %", xaxis_title=None)
    return fig


def fig_top_loss_feeders(df):
    fig = px.bar(
        df.sort_values("Avg_Loss_Pct"), x="Avg_Loss_Pct", y="Feeder_Name", color="Division",
        orientation="h", title="Feeders by Average Distribution Loss %",
    )
    fig.update_layout(xaxis_title="Avg Loss %", yaxis_title=None)
    return fig


def fig_top_loss_substations(df):
    fig = px.bar(
        df.sort_values("Avg_Loss_Pct"), x="Avg_Loss_Pct", y="Substation_Names", color="Division",
        orientation="h", title="Substations by Average Distribution Loss %",
    )
    fig.update_layout(xaxis_title="Avg Loss %", yaxis_title=None)
    return fig


def fig_loss_by_division(df):
    fig = px.bar(
        df.sort_values("Distribution_Loss_Pct"), x="Distribution_Loss_Pct", y="Division",
        orientation="h", title="Average Distribution Loss % by Division",
    )
    fig.update_layout(xaxis_title="Avg Loss %", yaxis_title=None)
    return fig


def fig_loss_by_dt_type(df):
    fig = px.bar(
        df.sort_values("Distribution_Loss_Pct"), x="Distribution_Loss_Pct", y="DT_type",
        orientation="h", title="Average Distribution Loss % by Transformer Type",
    )
    fig.update_layout(xaxis_title="Avg Loss %", yaxis_title=None)
    return fig


def fig_theft_trend(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Case_Count"], name="Cases Booked", mode="lines+markers"))
    fig.update_layout(
        title="Theft Cases Booked Over Time", xaxis_title=None, yaxis_title="Case Count",
    )
    return fig


def fig_theft_by_type(df):
    fig = px.pie(
        df, names="Theft_Type", values="Case_Count", title="Theft Cases by Type", hole=0.4,
    )
    return fig


def fig_theft_by_status(df):
    fig = px.bar(
        df, x="Case_Status", y="Case_Count", color="Case_Status", title="Theft Cases by Status",
    )
    fig.update_layout(xaxis_title=None, showlegend=False)
    return fig


def fig_top_theft_feeders(df, metric="Case_Count"):
    fig = px.bar(
        df.sort_values(metric), x=metric, y="Feeder_Name", color="Division",
        orientation="h", title=f"Feeders Ranked by {metric.replace('_', ' ')}",
    )
    fig.update_layout(yaxis_title=None)
    return fig


def fig_loss_vs_theft_scatter(merged_df, y="Case_Count"):
    fig = px.scatter(
        merged_df, x="Distribution_Loss_Pct", y=y,
        trendline="ols", title=f"Distribution Loss % vs {y.replace('_', ' ')} (monthly, per feeder)",
        hover_data=["Feeder_Name"],
    )
    fig.update_layout(xaxis_title="Avg Loss %", yaxis_title=y.replace("_", " "))
    return fig
