MODEL (
    name sqlmesh_example.example_incremental_model,
    kind INCREMENTAL_BY_TIME_RANGE (
        time_column ds
    ),
    start '2020-01-01',
    cron '@daily',
);

SELECT
    id,
    item_id,
    ds,
FROM
    (VALUES
        (1, 1, '2020-01-01'),
        (1, 2, '2020-01-01'),
        (2, 1, '2020-01-01'),
        (3, 3, '2020-01-03'),
        (4, 1, '2020-01-04'),
        (5, 1, '2020-01-05'),
        (6, 1, '2020-01-06'),
        (7, 1, '2020-01-07')
    ) AS t (id, item_id, ds)
WHERE
    ds between @start_ds and @end_ds
