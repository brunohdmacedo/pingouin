import numpy as np
import pandas as pd
from scipy.stats import t, norm
from pingouin.utils import _flatten_list

__all__ = ['linear_regression', 'logistic_regression', 'mediation_analysis']


def linear_regression(X, y, add_intercept=True, coef_only=False, alpha=0.05,
                      as_dataframe=True):
    """(Multiple) Linear regression.

    Parameters
    ----------
    X : np.array or list
        Predictor(s). Shape = (n_samples, n_features) or (n_samples,).
    y : np.array or list
        Dependent variable. Shape = (n_samples).
    add_intercept : bool
        If False, assume that the data are already centered. If True, add a
        constant term to the model. In this case, the first value in the
        output dict is the intercept of the model.
    coef_only : bool
        If True, return only the regression coefficients.
    alpha : float
        Alpha value used for the confidence intervals.
        CI = [alpha / 2 ; 1 - alpha / 2]
    as_dataframe : bool
        If True, returns a pandas DataFrame. If False, returns a dictionnary.

    Returns
    -------
    stats : dataframe or dict
        Linear regression summary::

        'names' : name of variable(s) in the model (e.g. x1, x2...)
        'coef' : regression coefficients
        'se' : standard error of the estimate
        'T' : T-values
        'pval' : p-values
        'r2' : coefficient of determination (R2)
        'adj_r2' : adjusted R2
        'CI[2.5%]' : lower confidence interval
        'CI[97.5%]' : upper confidence interval

    Notes
    -----
    The beta coefficients of the regression are estimated using the
    :py:func:`numpy.linalg.lstsq` function.

    It is generally recommanded to include a constant term (intercept) to the
    model to limit the bias and force the residual mean to equal zero.
    Note that intercept coefficient and p-values are however rarely meaningful.

    The standard error of the estimates is a measure of the accuracy of the
    prediction defined as:

    .. math:: se = \\sqrt{MSE \\cdot (X^TX)^{-1}}

    where :math:`MSE` is the mean squared error,

    .. math:: MSE = \\frac{\\sum{(true - pred)^2}}{n - p - 1}

    :math:`p` is the total number of explanatory variables in the model
    (excluding the intercept) and :math:`n` is the sample size.

    Using the coefficients and the standard errors, the T-values can be
    obtained:

    .. math:: T = \\frac{coef}{se}

    and the p-values can then be approximated using a T-distribution
    with :math:`n - p - 1` degrees of freedom.

    The coefficient of determination (:math:`R^2`) is defined as:

    .. math:: R^2 = 1 - (\\frac{SS_{resid}}{SS_{total}})

    The adjusted :math:`R^2` is defined as:

    .. math:: \\overline{R}^2 = 1 - (1 - R^2) \\frac{n - 1}{n - p - 1}

    Results have been compared against sklearn, statsmodels and JASP.

    This function will not run if NaN values are either present in the target
    or predictors variables. Please remove them before runing the function.

    Examples
    --------
    1. Simple linear regression

    >>> import numpy as np
    >>> from pingouin import linear_regression
    >>> np.random.seed(123)
    >>> mean, cov, n = [4, 6], [[1, 0.5], [0.5, 1]], 30
    >>> x, y = np.random.multivariate_normal(mean, cov, n).T
    >>> lm = linear_regression(x, y)
    >>> lm.round(2)
           names  coef    se     T  pval    r2  adj_r2  CI[2.5%]  CI[97.5%]
    0  Intercept  4.40  0.54  8.16  0.00  0.24    0.21      3.29       5.50
    1         x1  0.39  0.13  2.99  0.01  0.24    0.21      0.12       0.67

    2. Multiple linear regression

    >>> np.random.seed(42)
    >>> z = np.random.normal(size=n)
    >>> X = np.column_stack((x, z))
    >>> lm = linear_regression(X, y)
    >>> print(lm['coef'].values)
    [4.54123324 0.36628301 0.17709451]

    3. Using a Pandas DataFrame

    >>> import pandas as pd
    >>> df = pd.DataFrame({'x': x, 'y': y, 'z': z})
    >>> lm = linear_regression(df[['x', 'z']], df['y'])
    >>> print(lm['coef'].values)
    [4.54123324 0.36628301 0.17709451]

    4. No intercept and return coef only

    >>> linear_regression(X, y, add_intercept=False, coef_only=True)
    array([ 1.40935593, -0.2916508 ])

    5. Return a dictionnary instead of a DataFrame

    >>> lm_dict = linear_regression(X, y, as_dataframe=False)
    """
    # Extract names if X is a Dataframe or Series
    if isinstance(X, pd.DataFrame):
        names = X.keys().tolist()
    elif isinstance(X, pd.Series):
        names = [X.name]
    else:
        names = []

    assert 0 < alpha < 1

    # Convert input to numpy array
    X = np.asarray(X)
    y = np.asarray(y)

    if X.ndim == 1:
        # Convert to (n_samples, n_features) shape
        X = X[..., np.newaxis]

    # Check for NaN / Inf
    y_gd = np.isfinite(y).all()
    X_gd = np.isfinite(X).all()
    assert y_gd, 'Target (y) contains NaN or Inf. Please remove them.'
    assert X_gd, 'Predictors (X) contain NaN or Inf. Please remove them.'

    # Check that X and y have same length
    assert y.shape[0] == X.shape[0], 'X and y must have same number of samples'

    if not names:
        names = ['x' + str(i + 1) for i in range(X.shape[1])]

    if add_intercept:
        # Add intercept
        X = np.column_stack((np.ones(X.shape[0]), X))
        names.insert(0, "Intercept")

    # Compute beta coefficient and predictions
    coef = np.linalg.lstsq(X, y, rcond=None)[0]
    if coef_only:
        return coef
    pred = np.dot(X, coef)
    resid = np.square(y - pred)
    ss_res = resid.sum()

    n, p = X.shape[0], X.shape[1]
    # Degrees of freedom should not include the intercept
    dof = n - p if add_intercept else n - p - 1
    # Compute mean squared error, variance and SE
    MSE = ss_res / dof
    beta_var = MSE * (np.linalg.inv(np.dot(X.T, X)).diagonal())
    beta_se = np.sqrt(beta_var)

    # Compute R2, adjusted R2 and RMSE
    ss_tot = np.square(y - y.mean()).sum()
    # ss_exp = np.square(pred - y.mean()).sum()
    r2 = 1 - (ss_res / ss_tot)
    adj_r2 = 1 - (1 - r2) * (n - 1) / dof

    # Compute T and p-values
    T = coef / beta_se
    pval = np.array([2 * t.sf(np.abs(i), dof) for i in T])

    # Compute confidence intervals
    crit = t.ppf(1 - alpha / 2, dof)
    marg_error = crit * beta_se
    ll = coef - marg_error
    ul = coef + marg_error

    # Rename CI
    ll_name = 'CI[%.1f%%]' % (100 * alpha / 2)
    ul_name = 'CI[%.1f%%]' % (100 * (1 - alpha / 2))

    # Create dict
    stats = {'names': names, 'coef': coef, 'se': beta_se, 'T': T,
             'pval': pval, 'r2': r2, 'adj_r2': adj_r2, ll_name: ll,
             ul_name: ul}

    if as_dataframe:
        return pd.DataFrame.from_dict(stats)
    else:
        return stats


def logistic_regression(X, y, coef_only=False, alpha=0.05,
                        as_dataframe=True, **kwargs):
    """(Multiple) Binary logistic regression.

    Parameters
    ----------
    X : np.array or list
        Predictor(s). Shape = (n_samples, n_features) or (n_samples,).
    y : np.array or list
        Dependent variable. Shape = (n_samples).
        Must be binary.
    coef_only : bool
        If True, return only the regression coefficients.
    alpha : float
        Alpha value used for the confidence intervals.
        CI = [alpha / 2 ; 1 - alpha / 2]
    as_dataframe : bool
        If True, returns a pandas DataFrame. If False, returns a dictionnary.
    **kwargs : optional
        Optional arguments passed to sklearn.linear_model.LogisticRegression

    Returns
    -------
    stats : dataframe or dict
        Logistic regression summary::

        'names' : name of variable(s) in the model (e.g. x1, x2...)
        'coef' : regression coefficients
        'se' : standard error
        'z' : z-scores
        'pval' : two-tailed p-values
        'CI[2.5%]' : lower confidence interval
        'CI[97.5%]' : upper confidence interval

    Notes
    -----
    This is a wrapper around the sklearn.linear_model.LogisticRegression class.

    Results have been compared against statsmodels and JASP.

    Note that the first coefficient is always the constant term (intercept) of
    the model.

    This function will not run if NaN values are either present in the target
    or predictors variables. Please remove them before runing the function.

    Adapted from a code found at
    https://gist.github.com/rspeare/77061e6e317896be29c6de9a85db301d

    Examples
    --------
    1. Simple binary logistic regression

    >>> import numpy as np
    >>> from pingouin import logistic_regression
    >>> np.random.seed(123)
    >>> x = np.random.normal(size=30)
    >>> y = np.random.randint(0, 2, size=30)
    >>> lom = logistic_regression(x, y)
    >>> lom.round(2)
           names  coef    se     z  pval  CI[2.5%]  CI[97.5%]
    0  Intercept -0.27  0.37 -0.73  0.46     -0.99       0.45
    1         x1  0.06  0.32  0.19  0.85     -0.56       0.68

    2. Multiple binary logistic regression

    >>> np.random.seed(42)
    >>> z = np.random.normal(size=30)
    >>> X = np.column_stack((x, z))
    >>> lom = logistic_regression(X, y)
    >>> print(lom['coef'].values)
    [-0.34933805 -0.0226106  -0.39453532]

    3. Using a Pandas DataFrame

    >>> import pandas as pd
    >>> df = pd.DataFrame({'x': x, 'y': y, 'z': z})
    >>> lom = logistic_regression(df[['x', 'z']], df['y'])
    >>> print(lom['coef'].values)
    [-0.34933805 -0.0226106  -0.39453532]

    4. Return only the coefficients

    >>> logistic_regression(X, y, coef_only=True)
    array([-0.34933805, -0.0226106 , -0.39453532])

    4. Passing custom parameters to sklearn

    >>> lom = logistic_regression(X, y, solver='sag', max_iter=10000)
    >>> print(lom['coef'].values)
    [-0.34941889 -0.02261911 -0.39451064]
    """
    # Check that sklearn is installed
    from pingouin.utils import _is_sklearn_installed
    _is_sklearn_installed(raise_error=True)
    from sklearn.linear_model import LogisticRegression

    # Extract names if X is a Dataframe or Series
    if isinstance(X, pd.DataFrame):
        names = X.keys().tolist()
    elif isinstance(X, pd.Series):
        names = [X.name]
    else:
        names = []

    assert 0 < alpha < 1

    # Convert to numpy array
    X = np.asarray(X)
    y = np.asarray(y)

    if np.unique(y).size != 2:
        raise ValueError('Dependent variable must be binary.')

    # Add axis if only one-dimensional array
    if X.ndim == 1:
        X = X[..., np.newaxis]

    # Check for NaN /  Inf
    y_gd = np.isfinite(y).all()
    X_gd = np.isfinite(X).all()
    assert y_gd, 'Target variable contains NaN or Inf. Please remove them.'
    assert X_gd, 'Predictors contains NaN or Inf. Please remove them.'

    # Check that X and y have same length
    assert y.shape[0] == X.shape[0], 'X and y must have same number of samples'

    if not names:
        names = ['x' + str(i + 1) for i in range(X.shape[1])]

    # Add intercept in names
    names.insert(0, "Intercept")

    # Initialize and fit
    if 'solver' not in kwargs:
        kwargs['solver'] = 'lbfgs'
    if 'multi_class' not in kwargs:
        kwargs['multi_class'] = 'auto'
    lom = LogisticRegression(**kwargs)
    lom.fit(X, y)
    coef = np.append(lom.intercept_, lom.coef_)
    if coef_only:
        return coef

    # Design matrix -- add intercept
    X_design = np.column_stack((np.ones(X.shape[0]), X))
    n, p = X_design.shape

    # Fisher Information Matrix
    denom = (2 * (1 + np.cosh(lom.decision_function(X))))
    denom = np.tile(denom, (p, 1)).T
    fim = np.dot((X_design / denom).T, X_design)
    crao = np.linalg.inv(fim)

    # Standard error and Z-scores
    se = np.sqrt(np.diag(crao))
    z_scores = coef / se

    # Two-tailed p-values
    pval = np.array([2 * norm.sf(abs(z)) for z in z_scores])

    # Confidence intervals
    crit = norm.ppf(1 - alpha / 2)
    ll = coef - crit * se
    ul = coef + crit * se

    # Rename CI
    ll_name = 'CI[%.1f%%]' % (100 * alpha / 2)
    ul_name = 'CI[%.1f%%]' % (100 * (1 - alpha / 2))

    # Create dict
    stats = {'names': names, 'coef': coef, 'se': se, 'z': z_scores,
             'pval': pval, ll_name: ll, ul_name: ul}
    if as_dataframe:
        return pd.DataFrame.from_dict(stats)
    else:
        return stats


def _point_estimate(data, x, m, y, idx, mtype='linear'):
    """Point estimate of indirect effect based on bootstrap sample."""
    # Mediator(s) model (M(j) ~ X)
    beta_m = []
    for j in range(len(m)):
        # Mediator model (M ~ X)
        if mtype == 'linear':
            beta_m.append(linear_regression(data[x].iloc[idx],
                                            data[m[j]].iloc[idx],
                                            add_intercept=True,
                                            coef_only=True)[1])
        else:
            beta_m.append(logistic_regression(data[x].iloc[idx],
                                              data[m[j]].iloc[idx],
                                              coef_only=True)[1])

    # Full model (Y ~ X + M)
    beta_y = linear_regression(data[_flatten_list([x, m])].iloc[idx],
                               data[y].iloc[idx],
                               add_intercept=True,
                               coef_only=True)[2:]

    # Point estimate
    return beta_m * beta_y


def _bca(ab_estimates, sample_point, n_boot, alpha=0.05):
    """Get (1 - alpha) * 100 bias-corrected confidence interval estimate

    Note that this is similar to the "cper" module implemented in
    :py:func:`pingouin.compute_bootci`.

    Parameters
    ----------
    ab_estimates : 1d array-like
        Array with bootstrap estimates for each sample.
    sample_point : float
        Indirect effect point estimate based on full sample.
    n_boot : int
        Number of bootstrap samples
    alpha : float
        Alpha for confidence interval

    Returns
    -------
    CI : 1d array-like
        Lower limit and upper limit bias-corrected confidence interval
        estimates.
    """
    # Bias of bootstrap estimates
    z0 = norm.ppf(np.sum(ab_estimates < sample_point) / n_boot)

    # Adjusted intervals
    adjusted_ll = norm.cdf(2 * z0 + norm.ppf(alpha / 2)) * 100
    adjusted_ul = norm.cdf(2 * z0 + norm.ppf(1 - alpha / 2)) * 100
    ll = np.percentile(ab_estimates, q=adjusted_ll)
    ul = np.percentile(ab_estimates, q=adjusted_ul)
    return np.array([ll, ul])


def _pval_from_bootci(boot, estimate):
    """Compute p-value from bootstrap distribution.
    Similar to the pval function in the R package mediation.
    Note that this is less accurate than a permutation test because the
    bootstrap distribution is not conditioned on a true null hypothesis.
    """
    if estimate == 0:
        out = 1
    else:
        out = 2 * min(sum(boot > 0), sum(boot < 0)) / len(boot)
    return min(out, 1)


def mediation_analysis(data=None, x=None, m=None, y=None, alpha=0.05,
                       n_boot=500, seed=None, return_dist=False):
    """Mediation analysis using a bias-correct non-parametric bootstrap method.

    Parameters
    ----------
    data : pd.DataFrame
        Dataframe.
    x : str
        Column name in data containing the predictor variable.
        The predictor variable must be continuous.
    m : str or list of str
        Column name(s) in data containing the mediator variable(s).
        The mediator(s) can be continuous or binary (e.g. 0 or 1).
        This function supports multiple parallel mediators.
    y : str
        Column name in data containing the outcome variable.
        The outcome variable must be continuous.
    alpha : float
        Significance threshold. Used to determine the confidence interval,
        CI = [ alpha / 2 ; 1 -  alpha / 2]
    n_boot : int
        Number of bootstrap iterations for confidence intervals and p-values
        estimation. The greater, the slower.
    seed : int or None
        Random state seed.
    return_dist : bool
        If True, the function also returns the indirect bootstrapped beta
        samples (size = n_boot). Can be plotted for instance using
        :py:func:`seaborn.distplot()` or :py:func:`seaborn.kdeplot()`
        functions.

    Returns
    -------
    stats : pd.DataFrame
        Mediation summary::

        'path' : regression model
        'coef' : regression estimates
        'se' : standard error
        'CI[2.5%]' : lower confidence interval
        'CI[97.5%]' : upper confidence interval
        'pval' : two-sided p-values
        'sig' : statistical significance

    Notes
    -----
    Mediation analysis is a "statistical procedure to test
    whether the effect of an independent variable X on a dependent variable
    Y (i.e., X → Y) is at least partly explained by a chain of effects of the
    independent variable on an intervening mediator variable M and of the
    intervening variable on the dependent variable (i.e., X → M → Y)"
    (from Fiedler et al. 2011).

    The **indirect effect** (also referred to as average causal mediation
    effect or ACME) of X on Y through mediator M quantifies the estimated
    difference in Y resulting from a one-unit change in X through a sequence of
    causal steps in which X affects M, which in turn affects Y.
    It is considered significant if the specified confidence interval does not
    include 0. The path 'X --> Y' is the sum of both the indirect and direct
    effect. It is sometimes referred to as total effect. For more details,
    please refer to Fiedler et al 2011 or Hayes and Rockwood 2017.

    A linear regression is used if the mediator variable is continuous and a
    logistic regression if the mediator variable is dichotomous (binary). Note
    that this function also supports parallel multiple mediators: "in such
    models, mediators may be and often are correlated, but nothing in the
    model allows one mediator to causally influence another."
    (Hayes and Rockwood 2017)

    The two-sided p-value of the indirect effect is computed using the
    bootstrap distribution, as in the mediation R package. However, the p-value
    should be interpreted with caution since it is a) not constructed
    conditioned on a true null hypothesis (see Hayes and Rockwood 2017) and b)
    varies depending on the number of bootstrap samples and the random seed.

    Note that rows with NaN are automatically removed.

    Results have been tested against the R mediation package and this tutorial
    https://data.library.virginia.edu/introduction-to-mediation-analysis/

    References
    ----------
    .. [1] Baron, R. M. & Kenny, D. A. The moderator–mediator variable
           distinction in social psychological research: Conceptual, strategic,
           and statistical considerations. J. Pers. Soc. Psychol. 51, 1173–1182
           (1986).

    .. [2] Fiedler, K., Schott, M. & Meiser, T. What mediation analysis can
           (not) do. J. Exp. Soc. Psychol. 47, 1231–1236 (2011).

    .. [3] Hayes, A. F. & Rockwood, N. J. Regression-based statistical
           mediation and moderation analysis in clinical research:
           Observations, recommendations, and implementation. Behav. Res.
           Ther. 98, 39–57 (2017).

    .. [4] https://cran.r-project.org/web/packages/mediation/mediation.pdf

    .. [5] https://github.com/rmill040/pymediation

    Examples
    --------
    1. Simple mediation analysis

    >>> from pingouin import mediation_analysis, read_dataset
    >>> df = read_dataset('mediation')
    >>> mediation_analysis(data=df, x='X', m='M', y='Y', alpha=0.05, seed=42)
           path    coef      se          pval  CI[2.5%]  CI[97.5%]  sig
    0    X -> M  0.5610  0.0945  4.391362e-08    0.3735     0.7485  Yes
    1    M -> Y  0.6542  0.0858  1.612674e-11    0.4838     0.8245  Yes
    2     Total  0.3961  0.1112  5.671128e-04    0.1755     0.6167  Yes
    3    Direct  0.0396  0.1096  7.187429e-01   -0.1780     0.2572   No
    4  Indirect  0.3565  0.0833  0.000000e+00    0.2198     0.5377  Yes

    2. Return the indirect bootstrapped beta coefficients

    >>> stats, dist = mediation_analysis(data=df, x='X', m='M', y='Y',
    ...                                  return_dist=True)
    >>> print(dist.shape)
    (500,)

    3. Mediation analysis with a binary mediator variable

    >>> mediation_analysis(data=df, x='X', m='Mbin', y='Y', seed=42)
            path    coef      se      pval  CI[2.5%]  CI[97.5%]  sig
    0  X -> Mbin -0.0205  0.1159  0.859392   -0.2476     0.2066   No
    1  Mbin -> Y -0.1354  0.4118  0.743076   -0.9525     0.6818   No
    2      Total  0.3961  0.1112  0.000567    0.1755     0.6167  Yes
    3     Direct  0.3956  0.1117  0.000614    0.1739     0.6173  Yes
    4   Indirect  0.0023  0.0495  0.960000   -0.0715     0.1441   No

    4. Mediation analysis with multiple parallel mediators

    >>> np.random.seed(42)
    >>> df.rename(columns={"M": "M1"}, inplace=True)
    >>> df['M2'] = np.random.randint(0, 10, df.shape[0])
    >>> mediation_analysis(data=df, x='X', m=['M1', 'M2'], y='Y', seed=42)
              path    coef      se          pval  CI[2.5%]  CI[97.5%]  sig
    0      X -> M1  0.5610  0.0945  4.391362e-08    0.3735     0.7485  Yes
    1      X -> M2 -0.0435  0.1663  7.942276e-01   -0.3735     0.2865   No
    2      M1 -> Y  0.6580  0.0901  7.731809e-11    0.4793     0.8368  Yes
    3      M2 -> Y  0.0089  0.0596  8.821896e-01   -0.1095     0.1272   No
    4        Total  0.3961  0.1112  5.671128e-04    0.1755     0.6167  Yes
    5       Direct  0.0380  0.1114  7.336706e-01   -0.1832     0.2592   No
    6  Indirect M1  0.3584  0.0882  0.000000e+00    0.2124     0.5572  Yes
    7  Indirect M2 -0.0003  0.0105  9.400000e-01   -0.0285     0.0193   No
    """
    # Sanity check
    assert isinstance(x, str), 'y must be a string.'
    assert isinstance(y, str), 'y must be a string.'
    assert isinstance(m, (list, str)), 'Mediator(s) must be a list or string.'
    if isinstance(m, str):
        m = [m]
    n_mediator = len(m)
    assert isinstance(data, pd.DataFrame), 'Data must be a DataFrame.'
    # Check that columns are in dataframe
    columns = _flatten_list([x, m, y])
    keys = data.columns
    assert all([c in keys for c in columns]), 'Column(s) are not in DataFrame.'
    # Check that columns are numeric
    err_msg = "Columns must be numeric or boolean."
    assert all([data[c].dtype.kind in 'bfi' for c in columns]), err_msg

    # Drop rows with NAN Values
    data = data[columns].dropna()
    n = data.shape[0]
    assert n > 5, 'DataFrame must have at least 5 samples (rows).'

    # Check if mediator is binary
    mtype = 'logistic' if all(data[m].nunique() == 2) else 'linear'

    # Name of CI
    ll_name = 'CI[%.1f%%]' % (100 * alpha / 2)
    ul_name = 'CI[%.1f%%]' % (100 * (1 - alpha / 2))

    # Compute regressions
    cols = ['names', 'coef', 'se', 'pval', ll_name, ul_name]
    sxm = {}
    for j in m:
        if mtype == 'linear':
            sxm[j] = linear_regression(data[x], data[j], alpha=alpha,
                                       as_dataframe=True).loc[[1], cols]
        else:
            sxm[j] = logistic_regression(data[x], data[j], alpha=alpha,
                                         as_dataframe=True).loc[[1], cols]
        sxm[j].loc[1, 'names'] = 'X -> %s' % j

    sxm = pd.concat(sxm, ignore_index=True)

    smy = linear_regression(data[m], data[y], alpha=alpha).loc[1:, cols]

    # Average Total Effects
    sxy = linear_regression(data[x], data[y], alpha=alpha).loc[[1], cols]

    # Average Direct Effects
    direct = linear_regression(data[_flatten_list([x, m])], data[y],
                               alpha=alpha).loc[[1], cols]

    # Rename paths
    smy['names'] = smy['names'].apply(lambda x: '%s -> Y' % x)
    direct.loc[1, 'names'] = 'Direct'
    sxy.loc[1, 'names'] = 'Total'

    # Concatenate and create sig column
    stats = pd.concat((sxm, smy, sxy, direct), ignore_index=True)
    stats['sig'] = np.where(stats['pval'] < alpha, 'Yes', 'No')

    # Bootstrap confidence intervals
    rng = np.random.RandomState(seed)
    idx = rng.choice(np.arange(n), replace=True, size=(n_boot, n))
    ab_estimates = np.zeros(shape=(n_boot, n_mediator))
    for i in range(n_boot):
        ab_estimates[i, :] = _point_estimate(data, x=x, m=m, y=y,
                                             idx=idx[i, :], mtype=mtype)

    ab = _point_estimate(data, x=x, m=m, y=y, idx=np.arange(n), mtype=mtype)
    indirect = {'names': m, 'coef': ab, 'se': ab_estimates.std(ddof=1, axis=0),
                'pval': [], ll_name: [], ul_name: [], 'sig': []}

    for j in range(n_mediator):
        ci_j = _bca(ab_estimates[:, j], indirect['coef'][j],
                    alpha=alpha, n_boot=n_boot)
        indirect[ll_name].append(min(ci_j))
        indirect[ul_name].append(max(ci_j))
        # indirect['se'].append(ab_estimates[:, j].std(ddof=1))
        # Bootstrapped p-value of indirect effect
        # Note that this is less accurate than a permutation test because the
        # bootstrap distribution is not conditioned on a true null hypothesis.
        # For more details see Hayes and Rockwood. 2017
        indirect['pval'].append(_pval_from_bootci(ab_estimates[:, j],
                                indirect['coef'][j]))
        indirect['sig'].append('Yes' if indirect['pval'][j] < alpha else 'No')

    # Create output dataframe
    indirect = pd.DataFrame.from_dict(indirect)
    if n_mediator == 1:
        indirect['names'] = 'Indirect'
    else:
        indirect['names'] = indirect['names'].apply(lambda x:
                                                    'Indirect %s' % x)
    stats = stats.append(indirect, ignore_index=True)
    stats = stats.rename(columns={'names': 'path'})

    # Round
    col_to_round = ['coef', 'se', ll_name, ul_name]
    stats[col_to_round] = stats[col_to_round].round(4)

    if return_dist:
        return stats, np.squeeze(ab_estimates)
    else:
        return stats
